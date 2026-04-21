"""
loader
======
Carga y validación de datos FAERS via openFDA API.

Realiza llamadas paginadas a la API pública de openFDA para obtener
reportes de efectos adversos de un fármaco, los valida y los transforma
en un DataFrame listo para el análisis estratificado por sexo.

API base: https://api.fda.gov/drug/event.json
"""

import re
import time
import logging

import requests
import pandas as pd

from pharmawatch.exceptions import (
    SexFieldMissingError,
    InvalidDrugNameError,
    InsufficientDataError,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes del módulo
# ---------------------------------------------------------------------------

_BASE_URL = "https://api.fda.gov/drug/event.json"
_MAX_LIMIT = 100          # Máximo permitido por la API por llamada
_REQUEST_DELAY = 0.5      # Segundos entre llamadas para no exceder rate limit

# Expresión regular: nombre de fármaco — letras, números, espacios y guiones
_DRUG_NAME_RE = re.compile(r"^[a-zA-Z0-9\s\-\/\(\)\.]+$")

# Expresión regular: campo patientsex — solo '1' o '2'
_SEX_VALUE_RE = re.compile(r"^[12]$")

# Mapeo de valores de sexo de la API a etiquetas legibles
_SEX_MAP = {"1": "M", "2": "F"}


class FAERSLoader:
    """Carga reportes de efectos adversos desde la API openFDA.

    Realiza llamadas paginadas a openFDA, extrae los campos relevantes
    (reporte, sexo, fármaco, reacción) y los devuelve como un DataFrame
    limpio y validado.

    Parameters
    ----------
    drug_name : str
        Nombre del fármaco a consultar (ej: 'ibuprofen').
    max_records : int, optional
        Número máximo de reportes a descargar. Por defecto 1000.
    api_key : str, optional
        Clave de API de openFDA para mayor rate limit. Por defecto None.

    Attributes
    ----------
    drug_name : str
        Nombre del fármaco validado y en minúsculas.
    max_records : int
        Límite de registros a descargar.
    api_key : str or None
        Clave de API opcional.
    _raw_records : list
        Lista de registros crudos descargados (protegido).

    Examples
    --------
    >>> loader = FAERSLoader(drug_name="ibuprofen", max_records=500)
    >>> df = loader.load()
    >>> print(df.shape)
    >>> print(df["sex"].value_counts())
    """

    def __init__(self, drug_name: str, max_records: int = 1000, api_key: str = None):
        self.drug_name = self._validate_drug_name(drug_name)
        self.max_records = max_records
        self.api_key = api_key
        self._raw_records = []

    # ------------------------------------------------------------------
    # Métodos públicos
    # ------------------------------------------------------------------

    def load(self) -> pd.DataFrame:
        """Descarga, valida y transforma los reportes FAERS en DataFrame.

        Realiza llamadas paginadas a la API, aplana la estructura JSON
        anidada y valida el campo sexo.

        Returns
        -------
        pd.DataFrame
            DataFrame con columnas: report_id, sex, drug_name, reaction.
            Una fila por cada par (reporte, reacción).

        Raises
        ------
        InsufficientDataError
            Si la API devuelve menos de 10 registros para el fármaco.
        SexFieldMissingError
            Si más del 50% de filas tienen sexo inválido o ausente.
        requests.HTTPError
            Si la API devuelve un error HTTP.

        Examples
        --------
        >>> loader = FAERSLoader("ibuprofen", max_records=200)
        >>> df = loader.load()
        >>> df.head()
        """
        logger.info("Descargando reportes FAERS para '%s'...", self.drug_name)
        self._raw_records = self._fetch_all_pages()

        if len(self._raw_records) < 10:
            raise InsufficientDataError(self.drug_name, len(self._raw_records), 10)

        df = self._parse_records(self._raw_records)
        df = self._validate_sex_field(df)
        df = self._clean(df)

        logger.info(
            "Cargados %d registros para '%s' (%d mujeres, %d hombres).",
            len(df),
            self.drug_name,
            (df["sex"] == "F").sum(),
            (df["sex"] == "M").sum(),
        )
        return df

    def get_available_reactions(self, df: pd.DataFrame) -> pd.Series:
        """Devuelve las reacciones adversas más frecuentes del DataFrame.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame producido por load().

        Returns
        -------
        pd.Series
            Serie con el conteo de cada reacción, ordenada descendente.

        Examples
        --------
        >>> loader = FAERSLoader("ibuprofen")
        >>> df = loader.load()
        >>> loader.get_available_reactions(df).head(10)
        """
        return df["reaction"].value_counts()

    # ------------------------------------------------------------------
    # Métodos privados
    # ------------------------------------------------------------------

    def _validate_drug_name(self, drug_name: str) -> str:
        """Valida el nombre del fármaco con expresión regular.

        Parameters
        ----------
        drug_name : str
            Nombre a validar.

        Returns
        -------
        str
            Nombre en minúsculas si es válido.

        Raises
        ------
        InvalidDrugNameError
            Si el nombre no supera la expresión regular.
        """
        if not _DRUG_NAME_RE.match(drug_name.strip()):
            raise InvalidDrugNameError(drug_name)
        return drug_name.strip().lower()

    def _build_url(self, skip: int) -> str:
        """Construye la URL de la petición con paginación.

        Parameters
        ----------
        skip : int
            Número de registros a saltar (offset de paginación).

        Returns
        -------
        str
            URL completa con parámetros de búsqueda y paginación.
        """
        params = (
            f"search=patient.drug.medicinalproduct:\"{self.drug_name}\""
            f"&limit={_MAX_LIMIT}"
            f"&skip={skip}"
        )
        if self.api_key:
            params += f"&api_key={self.api_key}"
        return f"{_BASE_URL}?{params}"

    def _fetch_all_pages(self) -> list:
        """Descarga todos los registros paginando la API.

        Itera hasta alcanzar max_records o agotar los resultados
        disponibles en la API.

        Returns
        -------
        list
            Lista de registros crudos (dicts) de la API.

        Raises
        ------
        requests.HTTPError
            Si una petición falla con código de error HTTP.
        """
        records = []
        skip = 0

        while len(records) < self.max_records:
            url = self._build_url(skip)
            response = requests.get(url, timeout=30)

            # La API devuelve 404 cuando no hay más resultados
            if response.status_code == 404:
                logger.info("No hay más resultados en la API (skip=%d).", skip)
                break

            response.raise_for_status()
            data = response.json()

            batch = data.get("results", [])
            if not batch:
                break

            records.extend(batch)
            total_available = data["meta"]["results"]["total"]
            skip += _MAX_LIMIT

            logger.debug(
                "Descargados %d / %d registros (total API: %d).",
                len(records),
                self.max_records,
                total_available,
            )

            # Respetar rate limit de la API
            time.sleep(_REQUEST_DELAY)

            if skip >= total_available:
                break

        return records[:self.max_records]

    def _parse_records(self, records: list) -> pd.DataFrame:
        """Aplana los registros JSON anidados en un DataFrame tabular.

        Cada reacción adversa de un reporte genera una fila independiente.
        Un reporte con 3 reacciones produce 3 filas.

        Parameters
        ----------
        records : list
            Lista de dicts crudos de la API openFDA.

        Returns
        -------
        pd.DataFrame
            DataFrame con columnas: report_id, sex, drug_name, reaction.
        """
        rows = []
        for record in records:
            report_id = record.get("safetyreportid", "")
            sex_raw = record.get("patient", {}).get("patientsex", "")
            sex = _SEX_MAP.get(str(sex_raw), None)

            reactions = record.get("patient", {}).get("reaction", [])
            for rxn in reactions:
                reaction_name = rxn.get("reactionmeddrapt", "")
                if reaction_name:
                    rows.append({
                        "report_id": report_id,
                        "sex": sex,
                        "drug_name": self.drug_name,
                        "reaction": reaction_name.strip().lower(),
                    })

        return pd.DataFrame(rows)

    def _validate_sex_field(self, df: pd.DataFrame) -> pd.DataFrame:
        """Verifica que el campo sexo tenga suficientes valores válidos.

        Elimina filas con sexo nulo. Si más del 50% de filas no tienen
        sexo válido, lanza excepción.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame con columna 'sex'.

        Returns
        -------
        pd.DataFrame
            DataFrame sin filas de sexo nulo.

        Raises
        ------
        SexFieldMissingError
            Si más del 50% de filas tienen sexo nulo o inválido.
        """
        n_missing = df["sex"].isna().sum()
        pct_missing = n_missing / len(df) if len(df) > 0 else 1.0

        if pct_missing > 0.5:
            raise SexFieldMissingError(n_missing)

        return df.dropna(subset=["sex"])

    def _clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Limpia y normaliza el DataFrame final.

        - Elimina duplicados exactos
        - Resetea el índice
        - Convierte columnas a tipo string

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame validado.

        Returns
        -------
        pd.DataFrame
            DataFrame limpio y listo para el análisis.
        """
        df = df.drop_duplicates()
        df = df.reset_index(drop=True)
        df["drug_name"] = df["drug_name"].astype(str)
        df["reaction"] = df["reaction"].astype(str)
        df["sex"] = df["sex"].astype(str)
        return df
