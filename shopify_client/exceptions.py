class QueryError(Exception):
    pass


class RetriableException(Exception):
    pass


class BulkQueryInProgress(Exception):
    pass


class ThrottledException(RetriableException):
    pass


class ShopUnavailableException(Exception):
    pass


class InternalServerErrorException(RetriableException):
    pass
