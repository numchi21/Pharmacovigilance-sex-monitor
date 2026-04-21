"""
reference_finder
================
Búsqueda de fármacos de referencia similares via RxNorm API.

Dado un fármaco, busca otros fármacos similares por:
- Indicación terapéutica / enfermedad (DISEASE, rela=may_treat)
- Mecanismo de acción / clase farmacológica (MOA, rela=has_moa)

API utilizada: https://rxnav.nlm.nih.gov (NIH, gratuita, sin clave)
"""

import logging
import requests

logger = logging.getLogger(__name__)

_RXCLASS_BASE = "https://rxnav.nlm.nih.gov/REST/rxclass"
_TIMEOUT = 15

# Tipos de clase útiles y su rela correspondiente para búsqueda inversa
_CLASS_TYPE_RELA = {
    "DISEASE": "may_treat",
    "MOA": "has_moa",
    "PE": "has_pe",
}


class ReferenceFinder:
    """Busca fármacos de referencia similares a uno dado via RxNorm.

    Parameters
    ----------
    drug_name : str
        Nombre del fármaco base para buscar similares.

    Attributes
    ----------
    drug_name : str
        Fármaco base en minúsculas.
    _classes : list of dict or None
        Clases RxNorm del fármaco (protegido).

    Examples
    --------
    >>> finder = ReferenceFinder("ibuprofen")
    >>> finder.fetch_classes()
    >>> drugs = finder.get_similar_drugs(class_id="N0000175722", rela="has_moa", top_n=10)
    >>> print(drugs)
    """

    def __init__(self, drug_name: str):
        self.drug_name = drug_name.strip().lower()
        self._classes = None

    def fetch_classes(self) -> list:
        """Obtiene todas las clases RxNorm útiles del fármaco.

        Filtra solo las clases de tipo DISEASE (indicaciones),
        MOA (mecanismo de acción) y PE (efecto farmacológico),
        que son las que permiten encontrar fármacos realmente similares.

        Returns
        -------
        list of dict
            Lista de clases con keys: class_id, class_name,
            class_type, rela.

        Raises
        ------
        requests.HTTPError
            Si la API devuelve error.
        ValueError
            Si el fármaco no se encuentra en RxNorm.
        """
        url = f"{_RXCLASS_BASE}/class/byDrugName.json"
        params = {"drugName": self.drug_name, "relaSource": "MEDRT"}
        response = requests.get(url, params=params, timeout=_TIMEOUT)
        response.raise_for_status()

        data = response.json()
        raw = data.get("rxclassDrugInfoList", {}).get("rxclassDrugInfo", [])

        if not raw:
            raise ValueError(
                f"No se encontró '{self.drug_name}' en RxNorm. "
                "Comprueba que el nombre esté en inglés."
            )

        # Filtrar solo tipos útiles y con rela conocida
        self._classes = []
        seen = set()
        for c in raw:
            info = c["rxclassMinConceptItem"]
            class_type = info["classType"]
            rela = c.get("rela", "")
            class_id = info["classId"]

            if class_type not in _CLASS_TYPE_RELA:
                continue
            # Evitar duplicados por class_id
            if class_id in seen:
                continue
            seen.add(class_id)

            self._classes.append({
                "class_id": class_id,
                "class_name": info["className"],
                "class_type": class_type,
                "rela": rela,
            })

        return self._classes

    def get_disease_classes(self) -> list:
        """Devuelve clases de tipo DISEASE (indicaciones terapéuticas).

        Returns
        -------
        list of dict
            Clases de tipo DISEASE con rela=may_treat.
        """
        if self._classes is None:
            self.fetch_classes()
        return [c for c in self._classes if c["class_type"] == "DISEASE"]

    def get_moa_classes(self) -> list:
        """Devuelve clases de tipo MOA (mecanismo de acción).

        Returns
        -------
        list of dict
            Clases de tipo MOA con rela=has_moa.
        """
        if self._classes is None:
            self.fetch_classes()
        return [c for c in self._classes if c["class_type"] == "MOA"]

    def get_similar_drugs(self, class_id: str, rela: str, top_n: int = 10) -> list:
        """Obtiene fármacos similares a partir de un classId y rela RxNorm.

        Parameters
        ----------
        class_id : str
            ID de la clase RxNorm.
        rela : str
            Tipo de relación (ej: 'may_treat', 'has_moa').
        top_n : int, optional
            Número máximo de fármacos a devolver. Por defecto 10.

        Returns
        -------
        list of str
            Lista de nombres de fármacos similares en minúsculas,
            excluyendo el fármaco base.
        """
        url = f"{_RXCLASS_BASE}/classMembers.json"
        params = {
            "classId": class_id,
            "relaSource": "MEDRT",
            "rela": rela,
            "ttys": "IN",
        }
        response = requests.get(url, params=params, timeout=_TIMEOUT)
        response.raise_for_status()

        data = response.json()
        members = data.get("drugMemberGroup", {}).get("drugMember", [])

        drugs = [
            m["minConcept"]["name"].lower()
            for m in members
            if m["minConcept"]["name"].lower() != self.drug_name
        ]

        # Eliminar duplicados manteniendo orden
        seen = set()
        unique = []
        for d in drugs:
            if d not in seen:
                seen.add(d)
                unique.append(d)

        return unique[:top_n]
