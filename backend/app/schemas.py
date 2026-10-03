from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    email: str = ""
    password: str = ""


class RegisterIn(BaseModel):
    fullName: str = ""
    studentId: str = ""
    email: str = ""
    program: str = ""
    yearLevel: str = ""
    password: str = ""


class RefreshIn(BaseModel):
    refreshToken: str = ""


class PasswordResetRequestIn(BaseModel):
    email: str = ""


class PasswordResetConfirmIn(BaseModel):
    token: str = ""
    newPassword: str = ""


class ChangePasswordIn(BaseModel):
    currentPassword: str = ""
    newPassword: str = ""


class ProfileIn(BaseModel):
    program: str | None = None
    yearLevel: str | None = None


class StaffAccountIn(BaseModel):
    role: str = ""
    fullName: str = ""
    email: str = ""
    password: str = ""


class TermIn(BaseModel):
    trimester: str = ""
    academicYear: str = ""


class StatusIn(BaseModel):
    status: str = ""
    remarks: str = ""
    discountPercent: str = ""


class DiscountIn(BaseModel):
    discountPercent: str = ""


class ApplicationIn(BaseModel):
    program: str = ""
    yearLevel: str = ""
    scholarshipType: str = ""
    gwa: str = ""
    documents: dict | None = Field(default=None)
