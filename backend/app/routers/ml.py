from fastapi import APIRouter, Depends, HTTPException
from app.models.schemas import MLRequest, MLResult, UserPublic
from app.services.auth_service import get_current_user
from app.services.data_service import assert_dataset_access, outcome_missing_note
from app.services.history_service import record_history
from app.services.ml.boruta_service import run_boruta
from app.services.ml.lasso_service import run_lasso, run_lasso_screening, run_lasso_predict
from app.services.ml.tree_service import run_decision_tree
from app.services.ml.rf_service import run_random_forest
from app.services.ml.svm_service import run_svm
from app.services.ml.knn_service import run_knn
from app.services.ml.lda_qda_service import run_lda, run_qda
from app.services.ml.catboost_service import run_catboost
from app.services.ml.compare_service import run_compare
from app.services.ml.bkm_service import run_bkm
from app.services.ml.xgboost_service import run_xgboost
from app.services.ml.lightgbm_service import run_lightgbm
from app.services.ml.mlp_service import run_mlp
from app.services.ml.tabpfn_service import run_tabpfn
from app.services.ml.naive_bayes_service import run_naive_bayes
from app.services.ml.elastic_net_service import run_elastic_net
from app.services.ml.logistic_service import run_logistic, run_logistic_screening
from app.services.ml.cox_service import run_cox
from app.services.ml.diagnostics_service import run_vif
from app.services.ml.explain_service import run_shap, run_pdp
from app.services.ml.eval_service import run_calibration, run_dca
from app.services.ml.validation_service import run_bootstrap
from app.services.ml.nomogram_service import run_nomogram
from app.services.ml.predict_service import fit_context, predict_one
from app.services.ml.adv_diag_service import run_adv_diag

router = APIRouter(prefix="/api/ml", tags=["machine-learning"])


def _run(service_func, request: MLRequest, algorithm: str, current_user: UserPublic, fmt="svg"):
    try:
        assert_dataset_access(request.dataset_id, current_user.id)
        result = service_func(request, fmt)
        # E3f：所有建模结果统一注明结局缺失删除行数与 X 缺失填补约定
        note = outcome_missing_note(
            request.dataset_id, request.y_variable, request.x_variables,
            request.is_survival, request.time_variable, request.filters, current_user.id)
        result["summary"] = (str(result.get("summary", "")) + " " + note).strip()
        ml_result = MLResult(**result)
        record_history(current_user.id, algorithm, request, ml_result)
        return ml_result
    except ValueError as e:
        # E3g：未知模型 key 一律 422，不得静默回退
        if "不支持的模型类型" in str(e):
            raise HTTPException(status_code=422, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/boruta", response_model=MLResult)
def boruta(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_boruta, request, "boruta", current_user, request.params.get("format", "svg"))


@router.post("/compare", response_model=MLResult)
def compare(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_compare, request, "compare", current_user, request.params.get("format", "svg"))


@router.post("/lasso", response_model=MLResult)
def lasso(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_lasso, request, "lasso", current_user, request.params.get("format", "svg"))


@router.post("/lasso-screening", response_model=MLResult)
def lasso_screening(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_lasso_screening, request, "lasso-screening", current_user, request.params.get("format", "svg"))


@router.post("/lasso-predict", response_model=MLResult)
def lasso_predict(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_lasso_predict, request, "lasso-predict", current_user, request.params.get("format", "svg"))


@router.post("/elastic-net", response_model=MLResult)
def elastic_net(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_elastic_net, request, "elastic-net", current_user, request.params.get("format", "svg"))


@router.post("/logistic", response_model=MLResult)
def logistic(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_logistic, request, "logistic", current_user, request.params.get("format", "svg"))


@router.post("/logistic-screening", response_model=MLResult)
def logistic_screening(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_logistic_screening, request, "logistic-screening", current_user, request.params.get("format", "svg"))


@router.post("/cox", response_model=MLResult)
def cox(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_cox, request, "cox", current_user, request.params.get("format", "svg"))


@router.post("/bkm", response_model=MLResult)
def bkm(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_bkm, request, "bkm", current_user, request.params.get("format", "svg"))


@router.post("/decision-tree", response_model=MLResult)
def decision_tree(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_decision_tree, request, "decision-tree", current_user, request.params.get("format", "svg"))


@router.post("/random-forest", response_model=MLResult)
def random_forest(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_random_forest, request, "random-forest", current_user, request.params.get("format", "svg"))


@router.post("/xgboost", response_model=MLResult)
def xgboost(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_xgboost, request, "xgboost", current_user, request.params.get("format", "svg"))


@router.post("/lightgbm", response_model=MLResult)
def lightgbm(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_lightgbm, request, "lightgbm", current_user, request.params.get("format", "svg"))


@router.post("/svm", response_model=MLResult)
def svm(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_svm, request, "svm", current_user, request.params.get("format", "svg"))


@router.post("/knn", response_model=MLResult)
def knn(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_knn, request, "knn", current_user, request.params.get("format", "svg"))


@router.post("/lda", response_model=MLResult)
def lda(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_lda, request, "lda", current_user, request.params.get("format", "svg"))


@router.post("/qda", response_model=MLResult)
def qda(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_qda, request, "qda", current_user, request.params.get("format", "svg"))


@router.post("/catboost", response_model=MLResult)
def catboost(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_catboost, request, "catboost", current_user, request.params.get("format", "svg"))


@router.post("/mlp", response_model=MLResult)
def mlp(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_mlp, request, "mlp", current_user, request.params.get("format", "svg"))


@router.post("/tabpfn", response_model=MLResult)
def tabpfn(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_tabpfn, request, "tabpfn", current_user, request.params.get("format", "svg"))


@router.post("/naive-bayes", response_model=MLResult)
def naive_bayes(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_naive_bayes, request, "naive-bayes", current_user, request.params.get("format", "svg"))


@router.post("/vif", response_model=MLResult)
def vif(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_vif, request, "vif", current_user, request.params.get("format", "svg"))


@router.post("/shap", response_model=MLResult)
def shap_explain(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_shap, request, "shap", current_user, request.params.get("format", "svg"))


@router.post("/pdp", response_model=MLResult)
def pdp_explain(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_pdp, request, "pdp", current_user, request.params.get("format", "svg"))


@router.post("/calibration", response_model=MLResult)
def calibration(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_calibration, request, "calibration", current_user, request.params.get("format", "svg"))


@router.post("/dca", response_model=MLResult)
def dca(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_dca, request, "dca", current_user, request.params.get("format", "svg"))


@router.post("/bootstrap", response_model=MLResult)
def bootstrap(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_bootstrap, request, "bootstrap", current_user, request.params.get("format", "svg"))


@router.post("/nomogram", response_model=MLResult)
def nomogram(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_nomogram, request, "nomogram", current_user, request.params.get("format", "svg"))


@router.post("/predict")
def predict(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    """E3a：原始尺度单患者预测（Web 计算器用）。

    请求 = MLRequest + params.input（原始尺度的变量名 → 取值）。
    返回 {"probability": p, "linear_predictor": lp}。
    """
    try:
        assert_dataset_access(request.dataset_id, current_user.id)
        ctx = fit_context(request)
        return predict_one(ctx, (request.params or {}).get("input", {}))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/adv-diag", response_model=MLResult)
def adv_diag(request: MLRequest, current_user: UserPublic = Depends(get_current_user)):
    return _run(run_adv_diag, request, "adv-diag", current_user, request.params.get("format", "svg"))
