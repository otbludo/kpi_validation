"""Endpoints de validation des dossiers KYC."""
from typing import Union

from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.kyc_agent import kyc_agent
from app.api.v1.dependencies import get_kyc_form
from app.core.exceptions import InvalidSubmissionError, VisionAnalysisError
from app.core.logging import get_logger
from app.messages.errors import INTERNAL_SERVER_ERROR, INVALID_FORM_DATA
from app.schemas.kyc_input import KYCFormData
from app.schemas.kyc_output import DocumentQualityRejection, KYCOutputResponse
from app.security.dependencies import get_current_user

logger = get_logger(__name__)

router = APIRouter(prefix="/kyc", tags=["KYC"])


@router.post(
    "/process",
    status_code=status.HTTP_200_OK,
    response_model=Union[KYCOutputResponse, DocumentQualityRejection],
    summary="Valider un dossier KYC",
)
async def process_kyc_validation(
    # L'authentification est résolue en premier : un appelant anonyme ne
    # doit obtenir aucune information sur la validation du formulaire.
    current_user: dict = Depends(get_current_user),
    form_data: KYCFormData = Depends(get_kyc_form),
):
    """
    Analyse un dossier KYC et renvoie le verdict champ par champ.

    * **200** — ``KYCOutputResponse`` (analyse complète) ou
      ``DocumentQualityRejection`` (photos floues, analyse interrompue) ;
    * **400** — dossier incomplet ou illisible ;
    * **401 / 403** — authentification absente ou invalide ;
    * **502** — le modèle de vision n'a pas pu analyser le document ;
    * **500** — erreur inattendue (le détail est journalisé, non exposé).
    """
    try:
        result = await kyc_agent.process(form_data)
    except InvalidSubmissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_FORM_DATA.format(exc),
        ) from exc
    except VisionAnalysisError as exc:
        logger.error("Analyse du dossier %s impossible : %s", form_data.kyc_id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Erreur inattendue lors du traitement du dossier %s", form_data.kyc_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=INTERNAL_SERVER_ERROR,
        ) from exc

    if isinstance(result, DocumentQualityRejection):
        return result
    return KYCOutputResponse(donnees_output=result)
