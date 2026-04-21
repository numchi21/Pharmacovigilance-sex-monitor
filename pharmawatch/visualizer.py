"""
visualizer
==========
Visualizaciones matplotlib de señales de farmacovigilancia por sexo.

Genera dos gráficos a partir de los resultados de SexStratifiedAnalysis:
1. Comparativa entre los fármacos introducidos por el usuario
2. Ranking de todos los fármacos (analizados + referencia) con recomendación
"""

import textwrap
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd
import numpy as np

_COLOR_F = "#D4537E"
_COLOR_M = "#378ADD"
_COLOR_BG = "#F8F8F8"
_FONT_TITLE = {"fontsize": 13, "fontweight": "bold", "color": "#2C2C2A"}


class SignalVisualizer:
    """Genera visualizaciones de señales de farmacovigilancia por sexo.

    Parameters
    ----------
    results : pd.DataFrame
        DataFrame producido por SexStratifiedAnalysis.run().
    figsize : tuple, optional
        Tamaño base de las figuras. Por defecto (14, 8).

    Attributes
    ----------
    results : pd.DataFrame
        Resultados del análisis.
    figsize : tuple
        Tamaño de figuras.
    _drugs : list of str
        Lista de fármacos en los resultados (protegido).

    Examples
    --------
    >>> viz = SignalVisualizer(results=results)
    >>> viz.plot_user_drugs_comparison(drugs_to_analyze=["ibuprofen", "aspirin"])
    >>> viz.plot_drug_ranking(disease_label="Pain")
    """

    def __init__(self, results: pd.DataFrame, figsize: tuple = (14, 8)):
        self.results = results
        self.figsize = figsize
        self._drugs = results["drug_name"].unique().tolist()

    # ------------------------------------------------------------------
    # Gráfico 1 — Comparativa entre fármacos introducidos por el usuario
    # ------------------------------------------------------------------

    def plot_user_drugs_comparison(self, drugs_to_analyze: list,
                                    save_path: str = None) -> None:
        """Compara las señales PRR de los fármacos introducidos por el usuario.

        Muestra barras horizontales con las top reacciones de cada fármaco,
        separadas por sexo, con texto interpretativo automático.

        Parameters
        ----------
        drugs_to_analyze : list of str
            Fármacos introducidos por el usuario a comparar.
        save_path : str, optional
            Ruta para guardar. Si None muestra en pantalla.
        """
        self._apply_style()
        n = len(drugs_to_analyze)
        fig, axes = plt.subplots(
            1, n, figsize=(self.figsize[0] * n // max(n, 1), self.figsize[1]),
            sharey=False
        )
        fig.patch.set_facecolor(_COLOR_BG)
        if n == 1:
            axes = [axes]

        for ax, drug in zip(axes, drugs_to_analyze):
            drug_signals = self.results[
                (self.results["drug_name"] == drug) & self.results["is_signal"]
            ]
            female_df = drug_signals[drug_signals["sex"] == "F"].nlargest(8, "prr")
            male_df = drug_signals[drug_signals["sex"] == "M"].nlargest(8, "prr")

            reactions = list(dict.fromkeys(
                female_df["reaction"].tolist() + male_df["reaction"].tolist()
            ))[:8]

            prr_f = [
                female_df[female_df["reaction"] == r]["prr"].values[0]
                if r in female_df["reaction"].values else 0
                for r in reactions
            ]
            prr_m = [
                male_df[male_df["reaction"] == r]["prr"].values[0]
                if r in male_df["reaction"].values else 0
                for r in reactions
            ]

            y = np.arange(len(reactions))
            height = 0.35
            ax.set_facecolor(_COLOR_BG)
            ax.barh(y + height/2, prr_f, height, color=_COLOR_F, alpha=0.85, label="Mujeres")
            ax.barh(y - height/2, prr_m, height, color=_COLOR_M, alpha=0.85, label="Hombres")
            ax.set_yticks(y)
            ax.set_yticklabels([r.capitalize() for r in reactions], fontsize=9)
            ax.set_xlabel("PRR", fontsize=9)
            ax.set_title(drug.upper(), **_FONT_TITLE, pad=10)
            ax.axvline(x=2.0, color="#888780", linestyle="--", linewidth=0.8, alpha=0.6)
            ax.legend(fontsize=8, framealpha=0.5)
            ax.spines[["top", "right"]].set_visible(False)

        fig.suptitle("Comparativa de señales entre fármacos seleccionados",
                     fontsize=13, fontweight="bold", color="#2C2C2A", y=1.01)

        # Texto interpretativo global
        interpretation = self._interpret_user_drugs(drugs_to_analyze)
        fig.text(0.01, -0.04, interpretation, fontsize=8.5, color="#3d3d3a",
                 wrap=True,
                 bbox=dict(boxstyle="round,pad=0.5", facecolor="white",
                           edgecolor="#D3D1C7", alpha=0.85))

        plt.tight_layout()
        self._save_or_show(save_path)

    # ------------------------------------------------------------------
    # Gráfico 2 — Ranking de todos los fármacos con recomendación
    # ------------------------------------------------------------------

    def plot_drug_ranking(self, disease_label: str = "",
                           save_path: str = None) -> None:
        """Ranking comparativo de todos los fármacos por señales detectadas.

        Muestra una barra por fármaco y sexo con el total de señales,
        e indica cuál es el más seguro para mujeres y para hombres.

        Parameters
        ----------
        disease_label : str, optional
            Etiqueta de la enfermedad/indicación para el título.
        save_path : str, optional
            Ruta para guardar. Si None muestra en pantalla.
        """
        self._apply_style()

        signal_counts = (
            self.results[self.results["is_signal"]]
            .groupby(["drug_name", "sex"])
            .size()
            .reset_index(name="n_signals")
        )

        all_drugs = sorted(self.results["drug_name"].unique())
        x = np.arange(len(all_drugs))
        width = 0.35

        counts_f, counts_m, max_prr_f, max_prr_m = [], [], [], []
        for drug in all_drugs:
            f = signal_counts[(signal_counts["drug_name"] == drug) & (signal_counts["sex"] == "F")]
            m = signal_counts[(signal_counts["drug_name"] == drug) & (signal_counts["sex"] == "M")]
            counts_f.append(int(f["n_signals"].values[0]) if len(f) > 0 else 0)
            counts_m.append(int(m["n_signals"].values[0]) if len(m) > 0 else 0)

            df_f = self.results[(self.results["drug_name"] == drug) & (self.results["sex"] == "F") & self.results["is_signal"]]
            df_m = self.results[(self.results["drug_name"] == drug) & (self.results["sex"] == "M") & self.results["is_signal"]]
            max_prr_f.append(float(df_f["prr"].max()) if len(df_f) > 0 else 0.0)
            max_prr_m.append(float(df_m["prr"].max()) if len(df_m) > 0 else 0.0)

        fig, (ax_bar, ax_text) = plt.subplots(
            2, 1,
            figsize=(max(14, len(all_drugs) * 1.5), 9),
            gridspec_kw={"height_ratios": [3, 1]}
        )
        fig.patch.set_facecolor(_COLOR_BG)
        ax_bar.set_facecolor(_COLOR_BG)

        bars_f = ax_bar.bar(x - width/2, counts_f, width, color=_COLOR_F, alpha=0.85, label="Mujeres")
        bars_m = ax_bar.bar(x + width/2, counts_m, width, color=_COLOR_M, alpha=0.85, label="Hombres")

        for bar in bars_f:
            if bar.get_height() > 0:
                ax_bar.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
                            str(int(bar.get_height())), ha="center", va="bottom",
                            fontsize=8, color=_COLOR_F)
        for bar in bars_m:
            if bar.get_height() > 0:
                ax_bar.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
                            str(int(bar.get_height())), ha="center", va="bottom",
                            fontsize=8, color=_COLOR_M)

        ax_bar.set_xticks(x)
        ax_bar.set_xticklabels(
            [d.upper() for d in all_drugs], rotation=25, ha="right", fontsize=9
        )
        ax_bar.set_ylabel("Número de señales detectadas", fontsize=10)
        title = "Ranking de seguridad por fármaco y sexo"
        if disease_label:
            title += f"\n{disease_label}"
        ax_bar.set_title(title, **_FONT_TITLE, pad=12)
        ax_bar.legend(fontsize=9, framealpha=0.5)
        ax_bar.spines[["top", "right"]].set_visible(False)

        # Marcar los más seguros en negrita
        safest_f_idx = int(np.argmin(counts_f))
        safest_m_idx = int(np.argmin(counts_m))
        riskiest_f_idx = int(np.argmax(counts_f))
        riskiest_m_idx = int(np.argmax(counts_m))

        for i, label in enumerate(ax_bar.get_xticklabels()):
            if i == safest_f_idx:
                label.set_color(_COLOR_F)
                label.set_fontweight("bold")
            if i == safest_m_idx:
                label.set_color(_COLOR_M)
                label.set_fontweight("bold")

        # Texto interpretativo
        safest_f = all_drugs[safest_f_idx]
        safest_m = all_drugs[safest_m_idx]
        riskiest_f = all_drugs[riskiest_f_idx]
        riskiest_m = all_drugs[riskiest_m_idx]

        interpretation = (
            f"Para MUJERES: el fármaco con menos señales de riesgo es "
            f"{safest_f.upper()} ({counts_f[safest_f_idx]} señales). "
            f"El de mayor riesgo es {riskiest_f.upper()} "
            f"({counts_f[riskiest_f_idx]} señales, PRR máx. {max_prr_f[riskiest_f_idx]:.1f}).   "
            f"Para HOMBRES: el más seguro es {safest_m.upper()} "
            f"({counts_m[safest_m_idx]} señales). "
            f"El de mayor riesgo es {riskiest_m.upper()} "
            f"({counts_m[riskiest_m_idx]} señales, PRR máx. {max_prr_m[riskiest_m_idx]:.1f}).   "
            f"Nombre en negrita = fármaco más seguro para ese sexo."
        )

        ax_text.set_facecolor(_COLOR_BG)
        ax_text.axis("off")
        wrapped = textwrap.fill(interpretation, width=110)
        ax_text.text(
            0.01, 0.85, wrapped,
            transform=ax_text.transAxes,
            fontsize=9, color="#3d3d3a",
            verticalalignment="top",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="white",
                      edgecolor="#D3D1C7", alpha=0.8)
        )

        plt.tight_layout()
        self._save_or_show(save_path)

    # ------------------------------------------------------------------
    # Métodos privados
    # ------------------------------------------------------------------

    def _interpret_user_drugs(self, drugs_to_analyze: list) -> str:
        """Genera texto comparativo entre los fármacos del usuario.

        Parameters
        ----------
        drugs_to_analyze : list of str
            Fármacos a comparar.

        Returns
        -------
        str
            Texto interpretativo.
        """
        parts = []
        for drug in drugs_to_analyze:
            drug_signals = self.results[
                (self.results["drug_name"] == drug) & self.results["is_signal"]
            ]
            n_f = len(drug_signals[drug_signals["sex"] == "F"])
            n_m = len(drug_signals[drug_signals["sex"] == "M"])
            max_prr_f = drug_signals[drug_signals["sex"] == "F"]["prr"].max() if n_f > 0 else 0
            max_prr_m = drug_signals[drug_signals["sex"] == "M"]["prr"].max() if n_m > 0 else 0
            parts.append(
                f"{drug.upper()}: {n_f} señales en mujeres (PRR máx. {max_prr_f:.1f}) / "
                f"{n_m} señales en hombres (PRR máx. {max_prr_m:.1f})"
            )

        if len(drugs_to_analyze) > 1:
            # Cuál tiene menos señales para cada sexo
            signals_f = {
                d: len(self.results[(self.results["drug_name"] == d) &
                                     (self.results["sex"] == "F") &
                                     self.results["is_signal"]])
                for d in drugs_to_analyze
            }
            signals_m = {
                d: len(self.results[(self.results["drug_name"] == d) &
                                     (self.results["sex"] == "M") &
                                     self.results["is_signal"]])
                for d in drugs_to_analyze
            }
            safer_f = min(signals_f, key=signals_f.get)
            safer_m = min(signals_m, key=signals_m.get)
            parts.append(
                f"Entre los seleccionados: {safer_f.upper()} presenta menos señales "
                f"en mujeres y {safer_m.upper()} en hombres."
            )

        return "   ".join(parts)

    def _apply_style(self) -> None:
        """Aplica estilo matplotlib consistente."""
        try:
            plt.style.use("seaborn-v0_8-whitegrid")
        except OSError:
            plt.style.use("ggplot")

    def _save_or_show(self, save_path: str = None) -> None:
        """Guarda la figura o la muestra en pantalla.

        Parameters
        ----------
        save_path : str, optional
            Ruta de guardado. Si None llama a plt.show().
        """
        if save_path:
            plt.savefig(save_path, bbox_inches="tight", dpi=150,
                        facecolor=_COLOR_BG)
            plt.close()
        else:
            plt.show()
