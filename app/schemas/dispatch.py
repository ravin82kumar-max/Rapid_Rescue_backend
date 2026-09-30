from pydantic import BaseModel, Field


class DispatchRespondSchema(BaseModel):
    requestId: str = Field(..., description="Emergency request ID")
    action: str = Field(..., description="Action: ACCEPT, REJECT, or TIMEOUT")


class DispatchRespondResponse(BaseModel):
    success: bool = True
    requestId: str
    action: str


class DispatchCompleteSchema(BaseModel):
    requestId: str = Field(..., description="Emergency request ID")


class DispatchCompleteResponse(BaseModel):
    success: bool = True
    requestId: str
    status: str = "COMPLETED"
