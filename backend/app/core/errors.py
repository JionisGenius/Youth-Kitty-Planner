class ApiProblem(Exception):
    def __init__(self, status, code, message, *, details=None):
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def not_found():
    return ApiProblem(404, "NOT_FOUND", "요청한 리소스를 찾을 수 없습니다.")


def invalid(message="요청 값을 확인해 주세요."):
    return ApiProblem(422, "INVALID_ARGUMENT", message)

