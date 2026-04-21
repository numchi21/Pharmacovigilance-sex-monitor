"""
main
====
Pipeline interactivo de farmacovigilancia estratificada por sexo.
"""

import pandas as pd

from pharmawatch.loader import FAERSLoader
from pharmawatch.analyzer import SexStratifiedAnalysis
from pharmawatch.reference_finder import ReferenceFinder
from pharmawatch.visualizer import SignalVisualizer
from pharmawatch.exceptions import (
    InsufficientDataError,
    SexFieldMissingError,
    InvalidDrugNameError,
)


def _header():
    print("\n" + "="*62)
    print("   PHARMAWATCH — Farmacovigilancia con perspectiva de sexo")
    print("="*62)


def _ask(prompt: str, options: list = None) -> str:
    while True:
        print(prompt)
        val = input("  > ").strip().lower()
        if options is None or val in options:
            return val
        print(f"  Opción no válida. Elige entre: {', '.join(options)}")


def _ask_drugs(prompt: str) -> list:
    print(prompt)
    raw = input("  > ").strip()
    return [d.strip().lower() for d in raw.split(",") if d.strip()]


def step_select_drugs() -> list:
    drugs = _ask_drugs(
        "\n¿Qué fármaco(s) quieres analizar? "
        "(separa varios con comas, ej: ibuprofen, aspirin)"
    )
    if not drugs:
        print("  No has introducido ningún fármaco. Saliendo.")
        exit(0)
    return drugs


def step_reference(drugs_to_analyze: list) -> tuple:
    want_ref = _ask(
        "\n¿Quieres comparar con fármacos de referencia similares? (s/n)",
        options=["s", "n"],
    )
    if want_ref == "n":
        return [], ""

    criterion = _ask(
        "\n¿Por qué criterio quieres buscar similares?\n"
        "  [1] Enfermedad / síntoma que tratan\n"
        "  [2] Mecanismo de acción / clase farmacológica\n"
        "Introduce 1 o 2:",
        options=["1", "2"],
    )

    base_drug = drugs_to_analyze[0]
    print(f"\n  Buscando clases RxNorm para '{base_drug}'...")

    try:
        finder = ReferenceFinder(base_drug)
        finder.fetch_classes()
    except ValueError as e:
        print(f"  Error: {e}")
        return [], ""
    except Exception as e:
        print(f"  Error al conectar con RxNorm: {e}")
        return [], ""

    classes = finder.get_disease_classes() if criterion == "1" else finder.get_moa_classes()
    label = "enfermedad / síntoma" if criterion == "1" else "mecanismo de acción"

    if not classes:
        print(f"  No se encontraron clases de tipo '{label}'.")
        return [], ""

    print(f"\n  Clases disponibles por {label}:")
    for i, c in enumerate(classes, 1):
        print(f"  {i:>3}. {c['class_name']}")

    print(f"\n  ¿Qué clase quieres usar como referencia? (1-{len(classes)})")
    while True:
        try:
            idx = int(input("  > ").strip()) - 1
            if 0 <= idx < len(classes):
                selected_class = classes[idx]
                break
            print(f"  Introduce un número entre 1 y {len(classes)}.")
        except ValueError:
            print("  Introduce un número válido.")

    print("\n  ¿Cuántos fármacos de referencia quieres? (ej: 3, 5, 10, 50)")
    while True:
        try:
            top_n = int(input("  > ").strip())
            if top_n > 0:
                break
            print("  Introduce un número mayor que 0.")
        except ValueError:
            print("  Introduce un número válido.")

    print(f"\n  Buscando top {top_n} fármacos similares por '{selected_class['class_name']}'...")
    try:
        reference_drugs = finder.get_similar_drugs(
            class_id=selected_class["class_id"],
            rela=selected_class["rela"],
            top_n=top_n,
        )
    except Exception as e:
        print(f"  Error al buscar similares: {e}")
        return [], ""

    reference_drugs = [d for d in reference_drugs if d not in drugs_to_analyze]
    if not reference_drugs:
        print("  No se encontraron fármacos de referencia para esta clase.")
        return [], ""

    print(f"\n  Fármacos de referencia encontrados ({len(reference_drugs)}):")
    for d in reference_drugs:
        print(f"    - {d}")

    return reference_drugs, f"Indicación: {selected_class['class_name']}"


def step_load(all_drugs: list, max_records: int = 300) -> pd.DataFrame:
    print(f"\n  Descargando datos para {len(all_drugs)} fármaco(s)...\n")
    dfs = []
    for drug in all_drugs:
        print(f"  · {drug:<30}", end=" ", flush=True)
        try:
            loader = FAERSLoader(drug_name=drug, max_records=max_records)
            df = loader.load()
            dfs.append(df)
            print(f"{len(df):>5} registros  (F:{(df['sex']=='F').sum()} / M:{(df['sex']=='M').sum()})")
        except InvalidDrugNameError as e:
            print(f"NOMBRE INVÁLIDO — {e.message}")
        except InsufficientDataError as e:
            print(f"POCOS DATOS — {e.message}")
        except SexFieldMissingError as e:
            print(f"CAMPO SEXO AUSENTE — {e.message}")
        except Exception as e:
            print(f"ERROR — {e}")

    if not dfs:
        print("\n  No se pudo cargar ningún fármaco.")
        exit(1)

    full_df = pd.concat(dfs, ignore_index=True)
    print(f"\n  Total registros cargados: {len(full_df)}")
    return full_df


def step_analyze(full_df: pd.DataFrame, drugs_to_analyze: list,
                 all_drugs: list, has_reference: bool) -> pd.DataFrame:
    if not has_reference:
        print("\n  Modo sin comparativa — mostrando frecuencias de reacciones.\n")
        for drug in drugs_to_analyze:
            drug_df = full_df[full_df["drug_name"] == drug]
            print(f"\n{'='*62}")
            print(f"  {drug.upper()}  —  {len(drug_df)} reportes")
            print(f"{'='*62}")
            for sex, label in [("F", "MUJERES"), ("M", "HOMBRES")]:
                sex_df = drug_df[drug_df["sex"] == sex]
                top = sex_df["reaction"].value_counts().head(10)
                print(f"\n  {label} ({len(sex_df)} reportes) — top reacciones:")
                print(f"  {'Reacción':<40} {'Casos':>6}")
                print("  " + "-"*48)
                for rxn, n in top.items():
                    print(f"  {rxn:<40} {n:>6}")
        return pd.DataFrame()

    print("\n  Ejecutando análisis PRR + ROR estratificado por sexo...")

    # Filtrar fármacos sin suficientes datos antes del análisis
    valid_drugs = [d for d in all_drugs if len(full_df[full_df["drug_name"] == d]) >= 3]
    skipped = set(all_drugs) - set(valid_drugs)
    if skipped:
        print(f"  Fármacos omitidos por datos insuficientes: {', '.join(skipped)}")
    for d in drugs_to_analyze:
        if d not in valid_drugs:
            valid_drugs.append(d)

    try:
        analysis = SexStratifiedAnalysis(
            df=full_df,
            drug_filter=valid_drugs,
            prr_threshold=2.0,
            ci_level=0.95,
            min_records=3,
        )
        results = analysis.run()
    except InsufficientDataError as e:
        print(f"\n  Error: {e.message}")
        return pd.DataFrame()
    except Exception as e:
        print(f"\n  Error inesperado: {e}")
        return pd.DataFrame()

    signals = results[results["is_signal"]]
    for drug in drugs_to_analyze:
        drug_signals = signals[signals["drug_name"] == drug]
        print(f"\n{'='*62}")
        print(f"  {drug.upper()}")
        print(f"{'='*62}")
        for sex, label in [("F", "MUJERES"), ("M", "HOMBRES")]:
            sex_signals = drug_signals[drug_signals["sex"] == sex].sort_values(
                "prr", ascending=False
            )
            print(f"\n  {label} — {len(sex_signals)} señales detectadas:")
            if len(sex_signals) == 0:
                print("    (ninguna señal por encima del umbral)")
            else:
                print(f"  {'Reacción':<35} {'PRR':>6}  {'ROR':>6}  {'IC 95%':<22}  {'Casos':>5}")
                print("  " + "-"*75)
                for _, row in sex_signals.head(10).iterrows():
                    ic = f"[{row['ci_lower']:.2f}, {row['ci_upper']:.2f}]"
                    print(
                        f"  {row['reaction']:<35} "
                        f"{row['prr']:>6.2f}  "
                        f"{row['ror']:>6.2f}  "
                        f"{ic:<22}  "
                        f"{int(row['n_cases']):>5}"
                    )
    return results


def step_visualize(results: pd.DataFrame, drugs_to_analyze: list,
                   disease_label: str) -> None:
    if results.empty:
        return

    want_plots = _ask(
        "\n¿Quieres generar los gráficos? (s/n)",
        options=["s", "n"],
    )
    if want_plots == "n":
        return

    viz = SignalVisualizer(results)
    print("\n  Generando gráficos...")

    # Gráfico 1: comparativa entre los fármacos que escribió el usuario
    viz.plot_user_drugs_comparison(drugs_to_analyze=drugs_to_analyze)

    # Gráfico 2: ranking de todos los fármacos con recomendación
    viz.plot_drug_ranking(disease_label=disease_label)


def run_pipeline() -> None:
    """Ejecuta el pipeline interactivo completo."""
    _header()
    drugs_to_analyze = step_select_drugs()
    reference_drugs, disease_label = step_reference(drugs_to_analyze)
    has_reference = len(reference_drugs) > 0
    all_drugs = list(dict.fromkeys(drugs_to_analyze + reference_drugs))
    full_df = step_load(all_drugs)
    results = step_analyze(full_df, drugs_to_analyze, all_drugs, has_reference)
    step_visualize(results, drugs_to_analyze, disease_label)

    again = _ask("\n¿Quieres hacer otro análisis? (s/n)", options=["s", "n"])
    if again == "s":
        run_pipeline()
    else:
        print("\n  Hasta pronto.\n")


if __name__ == "__main__":
    run_pipeline()
