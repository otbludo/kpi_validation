from fastapi import APIRouter, Depends, HTTPException, status
from app.agents.kyc_agent import kyc_agent
from app.schemas.kyc_input import build_kyc_form_dependency
from app.schemas.kyc_output import KYCOutputResponse
from app.messages.errors import DONNEES_FORMULAIRE_INVALIDES, ERREUR_INFRASTRUCTURE_INTERNE

api_router = APIRouter()


@api_router.post("/kyc/process", response_model=KYCOutputResponse, status_code=status.HTTP_200_OK)
async def process_kyc_validation(form_data = Depends(build_kyc_form_dependency())):
    try:
        output_data = await kyc_agent.process(form_data)
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