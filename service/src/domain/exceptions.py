class DomainError(Exception):
    """Exceção base para erros de domínio do vehicle-core-service."""


class VehicleNotFoundError(DomainError):
    """Lançada quando o veículo informado não existe no catálogo."""


class VehicleNotEditableError(DomainError):
    """Lançada quando o veículo não está disponível e, portanto, não pode ser editado."""


class InvalidVehicleDataError(DomainError):
    """Lançada quando os dados de catálogo do veículo violam uma regra de negócio."""
