# Changelog

Todos los cambios notables realizados en el proyecto serán documentados en este archivo.

El formagto esta basado en: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
y este proyecto se adhiere a: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-04-21

### Added
- `visualizer.py`: método `plot_user_drugs_comparison()` — barras horizontales PRR por sexo
  con texto interpretativo automático comparando fármacos seleccionados por el usuario
- `visualizer.py`: método `plot_drug_ranking()` — ranking de seguridad de todos los fármacos
  (analizados + referencia) con indicación del más seguro para mujeres y hombres
- `docs/uml.png`: diagrama UML de la arquitectura de clases del paquete

### Changed
- `visualizer.py`: simplificado a dos gráficos (eliminados heatmap y panel de recomendación
  anteriores) según decisión de diseño

### Fixed
- `main.py`: eliminado prefijo `f` innecesario en string sin placeholders (ruff F541)
- `visualizer.py`: eliminado import no utilizado `matplotlib.patches` (ruff F401)

---

## [1.0.0] - 2026-04-20

### Added
- `visualizer.py`: métodos privados `_interpret_user_drugs()`, `_apply_style()`, `_save_or_show()`
- `main.py`: función `step_visualize()` que integra los dos gráficos en el pipeline interactivo

---

## [1.0.0] - 2026-04-19

### Added
- `main.py`: filtrado automático de fármacos sin datos suficientes antes del análisis
  (`valid_drugs`) con aviso al usuario

---

## [1.0.0] - 2026-04-18

### Added
- `demo_pharmawatch.ipynb`: notebook interactivo con `ipywidgets` para ejecución en
  Google Colab — widgets de texto, toggles, dropdowns, sliders y botones para todo el flujo

---

## [1.0.0] - 2026-04-17

### Changed
- `main.py`: `step_analyze()` ahora acepta `all_drugs` como parámetro y pasa todos los
  fármacos (analizados + referencia) al `SexStratifiedAnalysis` para calcular señales
  comparativas en todos ellos

---

## [1.0.0] - 2026-04-16

### Changed
- `main.py`: `step_reference()` devuelve tupla `(reference_drugs, disease_label)` en lugar
  de solo la lista, para pasar la etiqueta de indicación a los gráficos

---

## [0.4.0] - 2026-04-15

### Added
- `reference_finder.py`: clase `ReferenceFinder` con búsqueda de fármacos similares via
  RxNorm API (NIH) por dos criterios:
  - `get_disease_classes()`: clases de tipo DISEASE con `rela=may_treat`
  - `get_moa_classes()`: clases de tipo MOA con `rela=has_moa`
  - `get_similar_drugs()`: búsqueda inversa de miembros de una clase con deduplicación

---

## [0.4.0] - 2026-04-14

### Added
- `main.py`: función interactiva completa con flujo paso a paso en terminal:
  - `_header()`, `_ask()`, `_ask_drugs()` — helpers de UI
  - `step_select_drugs()` — selección de fármacos a analizar
  - `step_reference()` — búsqueda opcional de fármacos de referencia similares
  - `step_load()` — descarga con feedback por fármaco
  - `step_analyze()` — análisis y presentación de resultados en tabla
  - `run_pipeline()` — orquestación completa con opción de repetir análisis

---

## [0.4.0] - 2026-04-13

### Changed
- `reference_finder.py`: corregido el filtrado de clases útiles — se eliminan clases CHEM
  (que solo devuelven el mismo fármaco) y se añaden MOA y PE como tipos válidos
- `reference_finder.py`: `get_similar_drugs()` acepta ahora parámetro `rela` dinámico
  en lugar de hardcodeado, para soportar tanto `may_treat` como `has_moa`
- `main.py`: opción "principio activo" renombrada a "mecanismo de acción" y vinculada
  a `get_moa_classes()` en lugar de `get_chem_classes()`

### Fixed
- Corregido error en búsqueda por clase CHEM que devolvía 0 fármacos de referencia
- Corregido modo "sin comparativa" que no mostraba resultados al fallar la búsqueda
  de referencias

---

## [0.3.0] - 2026-04-12

### Added
- `analyzer.py`: clase abstracta `BaseAnalyzer` con patrón de herencia — define interfaz
  común con método abstracto `compute()` y métodos concretos `summary()`,
  `_check_min_records()`, `_filter_by_drug()`
- `analyzer.py`: clase `PRRAnalyzer(BaseAnalyzer)` — calcula Proportional Reporting Ratio
  estratificado por sexo con umbral configurable (`threshold=2.0`)
- `analyzer.py`: clase `RORAnalyzer(BaseAnalyzer)` — calcula Reporting Odds Ratio con
  intervalo de confianza configurable (`ci_level=0.95`) y corrección de Haldane
- `analyzer.py`: clase `SexStratifiedAnalysis` — patrón de composición que orquesta
  `PRRAnalyzer` y `RORAnalyzer`, combina resultados con Join y marca señales
- `analyzer.py`: soporte para análisis de uno o varios fármacos simultáneamente
  (`drug_filter` acepta `str` o `list`)
- `analyzer.py`: método `_get_z_score()` en `RORAnalyzer` para cálculo de IC

### Changed
- `analyzer.py`: atributo `drug_filter` normalizado internamente siempre como lista
  para simplificar la lógica de iteración

---

## [0.2.0] - 2026-04-11

### Added
- `loader.py`: clase `FAERSLoader` para descarga paginada desde openFDA API
  (`https://api.fda.gov/drug/event.json`)
- `loader.py`: método público `load()` — orquesta descarga, parseo, validación y limpieza
- `loader.py`: método público `get_available_reactions()` — top reacciones del DataFrame
- `loader.py`: método privado `_validate_drug_name()` — validación con expresión regular
  `_DRUG_NAME_RE = re.compile(r'^[a-zA-Z0-9\s\-\/$begin:math:text$$end:math:text$\.]+$')`
- `loader.py`: método privado `_build_url()` — construcción de URL con paginación y API key
- `loader.py`: método privado `_fetch_all_pages()` — paginación automática con rate limiting
  (`_REQUEST_DELAY = 0.5s`) hasta `max_records`
- `loader.py`: método privado `_parse_records()` — aplanado de JSON anidado a DataFrame
  tabular (una fila por par reporte-reacción)
- `loader.py`: método privado `_validate_sex_field()` — validación de campo sexo,
  lanza `SexFieldMissingError` si más del 50% de filas son inválidas
- `loader.py`: método privado `_clean()` — deduplicación y normalización del DataFrame
- `loader.py`: constantes de módulo `_BASE_URL`, `_MAX_LIMIT`, `_REQUEST_DELAY`,
  `_DRUG_NAME_RE`, `_SEX_VALUE_RE`, `_SEX_MAP`

### Changed
- Parámetros del constructor de `FAERSLoader` actualizados de `source_path/quarter`
  a `drug_name/max_records` para reflejar el uso de API en lugar de CSV

---

## [0.1.0] - 2026-04-10

### Added
- Estructura inicial del paquete siguiendo plantilla CEI:
  `pharmawatch/`, `tests/`, `setup.py`, `setup.cfg`, `VERSION.txt`
- `setup.cfg`: metadata del paquete, dependencias y configuración flake8
- `requirements.txt`: `pandas>=2.0`, `matplotlib>=3.7`, `requests>=2.31`, `numpy>=1.21`
- `requirements_dev.txt`: dependencias de desarrollo (`flake8`, `ruff`, `jupyter`)
- `LICENSE.md`: licencia MIT
- `README.md`: estructura con secciones de instalación, uso, módulos y fuente de datos
- `CHANGELOG.md`: inicializado con formato Keep a Changelog
- `exceptions.py`: jerarquía de excepciones personalizadas:
  - `PharmaWatchError(Exception)` — clase base
  - `InsufficientDataError(PharmaWatchError)` — datos insuficientes para señal
  - `SexFieldMissingError(PharmaWatchError)` — campo sexo ausente o inválido
  - `InvalidDrugNameError(PharmaWatchError)` — nombre de fármaco no válido
- `__init__.py`: metadatos del paquete (`__version__`, `__author__`, `__license__`)
- Esqueletos de `loader.py`, `analyzer.py`, `visualizer.py`, `main.py` con
  docstrings NumPy y estructura de clases definida
- Diagrama UML de la arquitectura de clases del paquete