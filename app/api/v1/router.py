from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from app.agents.kyc_agent import kyc_agent
from app.schemas.kyc_input import build_kyc_form_dependency
from app.schemas.kyc_output import KYCOutputResponse
from app.messages.errors import DONNEES_FORMULAIRE_INVALIDES, ERREUR_INFRASTRUCTURE_INTERNE
from app.security.dependencies import get_current_user

api_router = APIRouter()
security = HTTPBearer()


@api_router.post("/kyc/process", status_code=status.HTTP_200_OK)
async def process_kyc_validation(
    form_data = Depends(build_kyc_form_dependency()),
    current_user: dict = Depends(get_current_user),
):
    try:
        output_data = await kyc_agent.process(form_data)
        if isinstance(output_data, dict) and "message" in output_data:
            from fastapi.responses import JSONResponse
            return JSONResponse(content=output_data)
        return KYCOutputResponse(donnees_output=output_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=DONNEES_FORMULAIRE_INVALIDES.format(str(e)),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERREUR_INFRASTRUCTURE_INTERNE.format(str(e)),
        )