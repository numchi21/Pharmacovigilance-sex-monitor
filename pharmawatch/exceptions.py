"""
exceptions
==========
Excepciones personalizadas del paquete pharmawatch.
"""


class PharmaWatchError(Exception):
    """Excepción base del paquete pharmawatch.

    Parameters
    ----------
    message : str
        Mensaje descriptivo del error.
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class InsufficientDataError(PharmaWatchError):
    """Se lanza cuando el DataFrame no contiene suficientes registros
    para calcular una señal estadísticamente válida.

    Parameters
    ----------
    drug_name : str
        Nombre del fármaco para el que se intentó calcular la señal.
    n_records : int
        Número de registros encontrados.
    min_required : int
        Número mínimo de registros requeridos.

    Examples
    --------
    >>> raise InsufficientDataError("ibuprofen", 3, 10)
    InsufficientDataError: ibuprofen tiene 3 registros (mínimo: 10).
    """

    def __init__(self, drug_name: str, n_records: int, min_required: int):
        self.drug_name = drug_name
        self.n_records = n_records
        self.min_required = min_required
        message = (
            f"{drug_name} tiene {n_records} registros "
            f"(mínimo: {min_required})."
        )
        super().__init__(message)


class SexFieldMissingError(PharmaWatchError):
    """Se lanza cuando el campo de sexo del paciente está ausente
    o no contiene valores válidos ('M' / 'F') en el DataFrame.

    Parameters
    ----------
    n_missing : int
        Número de filas con campo sexo nulo o inválido.

    Examples
    --------
    >>> raise SexFieldMissingError(150)
    SexFieldMissingError: 150 filas sin campo sexo válido.
    """

    def __init__(self, n_missing: int):
        self.n_missing = n_missing
        message = f"{n_missing} filas sin campo sexo válido."
        super().__init__(message)


class InvalidDrugNameError(PharmaWatchError):
    """Se lanza cuando el nombre de fármaco proporcionado no supera
    la validación de formato (expresión regular).

    Parameters
    ----------
    drug_name : str
        Nombre del fármaco que no superó la validación.

    Examples
    --------
    >>> raise InvalidDrugNameError("123$$bad")
    InvalidDrugNameError: '123$$bad' no es un nombre de fármaco válido.
    """

    def __init__(self, drug_name: str):
        self.drug_name = drug_name
        message = f"'{drug_name}' no es un nombre de fármaco válido."
        super().__init__(message)
