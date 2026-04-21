"""
analyzer
========
Detección de señales de farmacovigilancia estratificadas por sexo.

Implementa los algoritmos estándar PRR (Proportional Reporting Ratio)
y ROR (Reporting Odds Ratio), calculados de forma independiente para
mujeres y hombres, para identificar señales diferenciales.

Soporta análisis de un único fármaco o comparación entre varios.

Referencias
-----------
Evans, S.J.W. et al. (2001). Use of proportional reporting ratios (PRRs)
for signal generation from spontaneous adverse drug reaction reports.
Pharmacoepidemiology and Drug Safety, 10(6), 483-486.
"""

from abc import ABC, abstractmethod
from typing import Union
import logging

import numpy as np
import pandas as pd

from pharmawatch.exceptions import InsufficientDataError

logger = logging.getLogger(__name__)


class BaseAnalyzer(ABC):
    """Clase base abstracta para analizadores de señales FAERS.

    Define la interfaz común que deben implementar todos los
    analizadores. Aplica el patrón de herencia: las subclases
    concretas implementan el método ``compute()``.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame con columnas: report_id, sex, drug_name, reaction.
    drug_filter : str or list of str
        Fármaco o lista de fármacos a analizar.
    min_records : int, optional
        Número mínimo de registros requeridos por fármaco. Por defecto 10.

    Attributes
    ----------
    df : pd.DataFrame
        DataFrame de entrada.
    drug_filter : list of str
        Lista de fármacos a analizar (siempre lista internamente).
    min_records : int
        Umbral mínimo de registros.
    _results : pd.DataFrame or None
        Resultados del análisis (protegido).
    """

    def __init__(
        self,
        df: pd.DataFrame,
        drug_filter: Union[str, list],
        min_records: int = 10,
    ):
        self.df = df
        self.drug_filter = [drug_filter] if isinstance(drug_filter, str) else drug_filter
        self.min_records = min_records
        self._results = None

    @abstractmethod
    def compute(self) -> pd.DataFrame:
        """Calcula la señal de farmacovigilancia.

        Returns
        -------
        pd.DataFrame
            DataFrame con resultados del análisis.

        Raises
        ------
        InsufficientDataError
            Si el número de registros es menor que min_records.
        """
        pass

    def summary(self) -> dict:
        """Devuelve un resumen de los resultados del análisis.

        Returns
        -------
        dict
            Diccionario con n_signals por sexo y top reacciones.

        Raises
        ------
        RuntimeError
            Si se llama antes de ejecutar compute().
        """
        if self._results is None:
            raise RuntimeError("Ejecuta compute() antes de llamar a summary().")

        summary = {}
        for drug in self.drug_filter:
            drug_df = self._results[self._results["drug_name"] == drug]
            signals = drug_df[drug_df["is_signal"]]
            summary[drug] = {
                "n_signals_female": len(signals[signals["sex"] == "F"]),
                "n_signals_male": len(signals[signals["sex"] == "M"]),
                "top_reaction_female": (
                    signals[signals["sex"] == "F"]
                    .sort_values("signal_score", ascending=False)["reaction"]
                    .iloc[0] if len(signals[signals["sex"] == "F"]) > 0 else None
                ),
                "top_reaction_male": (
                    signals[signals["sex"] == "M"]
                    .sort_values("signal_score", ascending=False)["reaction"]
                    .iloc[0] if len(signals[signals["sex"] == "M"]) > 0 else None
                ),
            }
        return summary

    def _check_min_records(self, drug: str) -> None:
        """Verifica que haya suficientes registros para un fármaco.

        Parameters
        ----------
        drug : str
            Nombre del fármaco a verificar.

        Raises
        ------
        InsufficientDataError
            Si el número de registros filtrados es insuficiente.
        """
        n = len(self.df[self.df["drug_name"] == drug])
        if n < self.min_records:
            raise InsufficientDataError(drug, n, self.min_records)

    def _filter_by_drug(self, drug: str) -> pd.DataFrame:
        """Filtra el DataFrame por un fármaco concreto.

        Parameters
        ----------
        drug : str
            Nombre del fármaco.

        Returns
        -------
        pd.DataFrame
            DataFrame filtrado.
        """
        return self.df[self.df["drug_name"] == drug].copy()


class PRRAnalyzer(BaseAnalyzer):
    """Calcula el PRR (Proportional Reporting Ratio) por sexo.

    El PRR mide cuánto más frecuente es una reacción adversa para un
    fármaco respecto al resto de fármacos en la base de datos, calculado
    de forma separada para mujeres y hombres.

    Fórmula
    -------
    PRR = (a / (a + b)) / (c / (c + d))

    Donde para cada par (fármaco, reacción, sexo):
        a = casos con el fármaco Y la reacción
        b = casos con el fármaco SIN la reacción
        c = casos SIN el fármaco CON la reacción
        d = casos SIN el fármaco SIN la reacción

    Se considera señal si PRR >= threshold Y a >= min_records.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame con columnas: report_id, sex, drug_name, reaction.
    drug_filter : str or list of str
        Fármaco o lista de fármacos a analizar.
    threshold : float, optional
        Umbral PRR para considerar señal. Por defecto 2.0.
    min_records : int, optional
        Mínimo de casos para considerar señal. Por defecto 10.

    Attributes
    ----------
    threshold : float
        Umbral de detección de señal.

    Examples
    --------
    >>> analyzer = PRRAnalyzer(df=df, drug_filter="ibuprofen", threshold=2.0)
    >>> results = analyzer.compute()
    >>> print(results[results["is_signal"]].head())
    """

    def __init__(
        self,
        df: pd.DataFrame,
        drug_filter: Union[str, list],
        threshold: float = 2.0,
        min_records: int = 10,
    ):
        super().__init__(df, drug_filter, min_records)
        self.threshold = threshold

    def compute(self) -> pd.DataFrame:
        """Calcula el PRR estratificado por sexo para cada fármaco.

        Returns
        -------
        pd.DataFrame
            DataFrame con columnas: drug_name, sex, reaction,
            n_cases, prr, signal_score, is_signal.

        Raises
        ------
        InsufficientDataError
            Si algún fármaco tiene menos registros que min_records.
        """
        all_results = []

        for drug in self.drug_filter:
            self._check_min_records(drug)
            drug_df = self._filter_by_drug(drug)

            for sex in ["F", "M"]:
                sex_df = self.df[self.df["sex"] == sex]
                drug_sex_df = drug_df[drug_df["sex"] == sex]

                # Conteo de reacciones para el fármaco filtrado por sexo
                drug_reactions = (
                    drug_sex_df.groupby("reaction")["report_id"]
                    .nunique()
                    .reset_index()
                    .rename(columns={"report_id": "a"})
                )

                # Total de reportes con el fármaco para ese sexo
                n_drug_sex = drug_sex_df["report_id"].nunique()

                # Total de reportes SIN el fármaco para ese sexo
                other_sex_df = sex_df[sex_df["drug_name"] != drug]
                n_other_sex = other_sex_df["report_id"].nunique()

                # Conteo de reacciones en reportes SIN el fármaco
                other_reactions = (
                    other_sex_df.groupby("reaction")["report_id"]
                    .nunique()
                    .reset_index()
                    .rename(columns={"report_id": "c"})
                )

                # Combinar con join
                merged = drug_reactions.merge(other_reactions, on="reaction", how="left")
                merged["c"] = merged["c"].fillna(0)
                merged["b"] = n_drug_sex - merged["a"]
                merged["d"] = n_other_sex - merged["c"]

                # Calcular PRR evitando división por cero
                merged["prr"] = np.where(
                    (merged["c"] > 0) & (n_other_sex > 0),
                    (merged["a"] / n_drug_sex) / (merged["c"] / n_other_sex),
                    np.nan,
                )

                merged["drug_name"] = drug
                merged["sex"] = sex
                merged["n_cases"] = merged["a"]
                merged["signal_score"] = merged["prr"]
                merged["is_signal"] = (
                    (merged["prr"] >= self.threshold) &
                    (merged["n_cases"] >= self.min_records)
                )

                all_results.append(
                    merged[["drug_name", "sex", "reaction", "n_cases",
                             "prr", "signal_score", "is_signal"]]
                )

        self._results = pd.concat(all_results, ignore_index=True)
        logger.info(
            "PRR calculado: %d señales detectadas.",
            self._results["is_signal"].sum(),
        )
        return self._results


class RORAnalyzer(BaseAnalyzer):
    """Calcula el ROR (Reporting Odds Ratio) por sexo con IC.

    El ROR es una medida de asociación entre un fármaco y una reacción
    adversa, análoga al odds ratio en epidemiología. Incluye intervalo
    de confianza: se considera señal cuando el límite inferior del IC
    es mayor que 1.

    Fórmula
    -------
    ROR = (a * d) / (b * c)
    SE(ln ROR) = sqrt(1/a + 1/b + 1/c + 1/d)
    IC_lower = exp(ln(ROR) - z * SE)
    IC_upper = exp(ln(ROR) + z * SE)

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame con columnas: report_id, sex, drug_name, reaction.
    drug_filter : str or list of str
        Fármaco o lista de fármacos a analizar.
    ci_level : float, optional
        Nivel de confianza para el IC. Por defecto 0.95.
    min_records : int, optional
        Mínimo de casos para considerar señal. Por defecto 10.

    Attributes
    ----------
    ci_level : float
        Nivel de confianza del intervalo.

    Examples
    --------
    >>> analyzer = RORAnalyzer(df=df, drug_filter="ibuprofen", ci_level=0.95)
    >>> results = analyzer.compute()
    >>> print(results[results["is_signal"]].head())
    """

    def __init__(
        self,
        df: pd.DataFrame,
        drug_filter: Union[str, list],
        ci_level: float = 0.95,
        min_records: int = 10,
    ):
        super().__init__(df, drug_filter, min_records)
        self.ci_level = ci_level
        self._z = self._get_z_score(ci_level)

    def compute(self) -> pd.DataFrame:
        """Calcula el ROR estratificado por sexo con intervalo de confianza.

        Returns
        -------
        pd.DataFrame
            DataFrame con columnas: drug_name, sex, reaction, n_cases,
            ror, ci_lower, ci_upper, signal_score, is_signal.

        Raises
        ------
        InsufficientDataError
            Si algún fármaco tiene menos registros que min_records.
        """
        all_results = []

        for drug in self.drug_filter:
            self._check_min_records(drug)
            drug_df = self._filter_by_drug(drug)

            for sex in ["F", "M"]:
                sex_df = self.df[self.df["sex"] == sex]
                drug_sex_df = drug_df[drug_df["sex"] == sex]

                drug_reactions = (
                    drug_sex_df.groupby("reaction")["report_id"]
                    .nunique()
                    .reset_index()
                    .rename(columns={"report_id": "a"})
                )

                n_drug_sex = drug_sex_df["report_id"].nunique()
                other_sex_df = sex_df[sex_df["drug_name"] != drug]
                n_other_sex = other_sex_df["report_id"].nunique()

                other_reactions = (
                    other_sex_df.groupby("reaction")["report_id"]
                    .nunique()
                    .reset_index()
                    .rename(columns={"report_id": "c"})
                )

                merged = drug_reactions.merge(other_reactions, on="reaction", how="left")
                merged["c"] = merged["c"].fillna(0.5)  # corrección de Haldane
                merged["b"] = n_drug_sex - merged["a"]
                merged["d"] = n_other_sex - merged["c"]

                # Evitar ceros con corrección de Haldane
                for col in ["a", "b", "c", "d"]:
                    merged[col] = merged[col].replace(0, 0.5)

                # Calcular ROR e intervalo de confianza
                merged["ror"] = (merged["a"] * merged["d"]) / (merged["b"] * merged["c"])
                merged["se_log_ror"] = np.sqrt(
                    1/merged["a"] + 1/merged["b"] + 1/merged["c"] + 1/merged["d"]
                )
                merged["ci_lower"] = np.exp(
                    np.log(merged["ror"]) - self._z * merged["se_log_ror"]
                )
                merged["ci_upper"] = np.exp(
                    np.log(merged["ror"]) + self._z * merged["se_log_ror"]
                )

                merged["drug_name"] = drug
                merged["sex"] = sex
                merged["n_cases"] = merged["a"]
                merged["signal_score"] = merged["ror"]
                merged["is_signal"] = (
                    (merged["ci_lower"] > 1.0) &
                    (merged["n_cases"] >= self.min_records)
                )

                all_results.append(
                    merged[["drug_name", "sex", "reaction", "n_cases",
                             "ror", "ci_lower", "ci_upper", "signal_score", "is_signal"]]
                )

        self._results = pd.concat(all_results, ignore_index=True)
        logger.info(
            "ROR calculado: %d señales detectadas.",
            self._results["is_signal"].sum(),
        )
        return self._results

    def _get_z_score(self, ci_level: float) -> float:
        """Devuelve el valor z para el nivel de confianza dado.

        Parameters
        ----------
        ci_level : float
            Nivel de confianza (ej: 0.95, 0.99).

        Returns
        -------
        float
            Valor z correspondiente.

        Raises
        ------
        ValueError
            Si ci_level no está entre 0 y 1.
        """
        if not 0 < ci_level < 1:
            raise ValueError(f"ci_level debe estar entre 0 y 1, recibido: {ci_level}")
        z_table = {0.90: 1.645, 0.95: 1.960, 0.99: 2.576}
        return z_table.get(ci_level, 1.960)


class SexStratifiedAnalysis:
    """Análisis completo estratificado por sexo combinando PRR y ROR.

    Implementa el patrón de composición: contiene instancias de
    PRRAnalyzer y RORAnalyzer y orquesta su ejecución conjunta.

    Acepta uno o varios fármacos para análisis comparativo.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame con columnas: report_id, sex, drug_name, reaction.
    drug_filter : str or list of str
        Fármaco o lista de fármacos a analizar.
    prr_threshold : float, optional
        Umbral PRR para señal. Por defecto 2.0.
    ci_level : float, optional
        Nivel de confianza ROR. Por defecto 0.95.
    min_records : int, optional
        Mínimo de registros requeridos. Por defecto 10.

    Attributes
    ----------
    drug_filter : list of str
        Lista de fármacos analizados.
    _prr_analyzer : PRRAnalyzer
        Analizador PRR (protegido).
    _ror_analyzer : RORAnalyzer
        Analizador ROR (protegido).

    Examples
    --------
    >>> # Un solo fármaco
    >>> analysis = SexStratifiedAnalysis(df=df, drug_filter="ibuprofen")
    >>> results = analysis.run()

    >>> # Varios fármacos
    >>> analysis = SexStratifiedAnalysis(
    ...     df=df, drug_filter=["ibuprofen", "aspirin"]
    ... )
    >>> results = analysis.run()
    >>> analysis.summary()
    """

    def __init__(
        self,
        df: pd.DataFrame,
        drug_filter: Union[str, list],
        prr_threshold: float = 2.0,
        ci_level: float = 0.95,
        min_records: int = 10,
    ):
        self.drug_filter = [drug_filter] if isinstance(drug_filter, str) else drug_filter
        self._prr_analyzer = PRRAnalyzer(df, drug_filter, prr_threshold, min_records)
        self._ror_analyzer = RORAnalyzer(df, drug_filter, ci_level, min_records)

    def run(self) -> pd.DataFrame:
        """Ejecuta ambos analizadores y combina los resultados.

        Returns
        -------
        pd.DataFrame
            DataFrame con resultados PRR y ROR combinados por
            drug_name, sex y reaction.

        Raises
        ------
        InsufficientDataError
            Si algún fármaco no tiene suficientes registros.
        """
        prr_results = self._prr_analyzer.compute()
        ror_results = self._ror_analyzer.compute()

        # Join de PRR y ROR por drug_name, sex, reaction
        combined = prr_results[
            ["drug_name", "sex", "reaction", "n_cases", "prr", "is_signal"]
        ].merge(
            ror_results[["drug_name", "sex", "reaction", "ror", "ci_lower", "ci_upper"]],
            on=["drug_name", "sex", "reaction"],
            how="inner",
        )

        # Una reacción se marca como señal si la detecta PRR O ROR
        combined["is_signal_prr"] = combined["is_signal"]
        ror_signal = ror_results[["drug_name", "sex", "reaction", "is_signal"]].rename(
            columns={"is_signal": "is_signal_ror"}
        )
        combined = combined.merge(
            ror_signal, on=["drug_name", "sex", "reaction"], how="left"
        )
        combined["is_signal"] = combined["is_signal_prr"] | combined["is_signal_ror"]
        combined = combined.drop(columns=["is_signal_prr"])
        combined = combined.sort_values(
            ["drug_name", "sex", "prr"], ascending=[True, True, False]
        ).reset_index(drop=True)

        logger.info(
            "Análisis combinado: %d señales totales para %d fármacos.",
            combined["is_signal"].sum(),
            len(self.drug_filter),
        )
        return combined

    def summary(self) -> dict:
        """Resumen ejecutivo del análisis estratificado.

        Returns
        -------
        dict
            Resultados PRR y ROR combinados por fármaco y sexo.

        Raises
        ------
        RuntimeError
            Si se llama antes de ejecutar run().
        """
        prr_summary = self._prr_analyzer.summary()
        ror_summary = self._ror_analyzer.summary()

        combined_summary = {}
        for drug in self.drug_filter:
            combined_summary[drug] = {
                "prr": prr_summary.get(drug, {}),
                "ror": ror_summary.get(drug, {}),
            }
        return combined_summary
