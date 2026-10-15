import pandas as pd
import numpy as np
from sklearn.linear_model import LassoCV, Lasso, LogisticRegressionCV, LogisticRegression, lasso_path
from sklearn.preprocessing import StandardScaler
from app.services.data_service import get_data_for_ml
from app.services.ml.utils import encode_figure, classification_metrics, regression_metrics, ChartData, TableData
from app.services.core.preprocessing import ClinicalPreprocessor, encode_y
from app.services.core.validation import train_test_pipeline
import matplotlib.pyplot as plt


def _plot_lasso_path(X_scaled: pd.DataFrame, y: pd.Series, alphas, is_classifier: bool, seed: int, fmt: str) -> ChartData:
    fig, ax = plt.subplots(figsize=(9, 6))
    if is_classifier:
        cs = np.asarray(alphas, dtype=float)
        lambdas = 1.0 / cs
        coefs = []
        for c in cs:
            path_model = LogisticRegression(C=c, penalty='l1', solver='saga', random_state=seed, max_iter=5000)
            path_model.fit(X_scaled, y)
            coef = path_model.coef_
            if coef.ndim > 1:
                coef = coef[0]
            coefs.append(coef)
        coefs = np.asarray(coefs)
        order = np.argsort(lambdas)[::-1]
        x_vals = np.log(lambdas[order])
        coefs = coefs[order]
    else:
        alphas_path, coefs, _ = lasso_path(X_scaled, y, alphas=np.asarray(alphas, dtype=float), max_iter=5000)
        x_vals = np.log(alphas_path)
        coefs = coefs.T

    for i, col in enumerate(X_scaled.columns):
        ax.plot(x_vals, coefs[:, i], lw=1, label=col if i < 12 else None)
    ax.axhline(0, color='black', linewidth=0.8, linestyle='--')
    ax.set_xlabel('Log Lambda')
    ax.set_ylabel('Coefficients')
    ax.set_title('LASSO Coefficient Path')
    if X_scaled.shape[1] <= 12:
        ax.legend(fontsize=8, loc='best')
    return ChartData(title="LASSO系数路径图", data=encode_figure(fig, fmt), type=fmt)


def _plot_lasso_cv(model, is_classifier: bool, best_alpha: float, cv: int, fmt: str) -> ChartData:
    fig, ax = plt.subplots(figsize=(8, 6))
    if is_classifier:
        cs = np.asarray(model.Cs_, dtype=float)
        lambdas = 1.0 / cs
        score_matrix = next(iter(model.scores_.values()))
        mean_error = 1 - score_matrix.mean(axis=0)
        se_error = score_matrix.std(axis=0) / np.sqrt(cv)
        order = np.argsort(lambdas)[::-1]
        x_vals = np.log(lambdas[order])
        mean_vals = mean_error[order]
        se_vals = se_error[order]
        y_label = 'Cross-Validation Error'
    else:
        lambdas = np.asarray(model.alphas_, dtype=float)
        mean_vals = model.mse_path_.mean(axis=1)
        se_vals = model.mse_path_.std(axis=1) / np.sqrt(cv)
        x_vals = np.log(lambdas)
        y_label = 'Mean Squared Error'

    ax.errorbar(x_vals, mean_vals, yerr=se_vals, fmt='o-', color='#3498db', ecolor='lightgray', capsize=2)
    ax.axvline(np.log(best_alpha), color='red', linestyle='--', label=f'lambda.min={best_alpha:.4g}')
    ax.set_xlabel('Log Lambda')
    ax.set_ylabel(y_label)
    ax.set_title(f'LASSO {cv}-Fold Cross-Validation')
    ax.legend()
    return ChartData(title=f"LASSO {cv}折交叉验证图", data=encode_figure(fig, fmt), type=fmt)

def run_lasso(request, fmt="svg"):
    df = get_data_for_ml(
        request.dataset_id, request.y_variable, request.x_variables,
        request.is_survival, request.time_variable, request.filters
    )
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    # 筛选类函数无留出验证，不存在泄漏；改用 ClinicalPreprocessor 保证编码一致
    X_df = df[list(request.x_variables)]
    prep = ClinicalPreprocessor(request.variable_types).fit(X_df)
    X = prep.transform(X_df)
    y, le = encode_y(df[request.y_variable], request.variable_types)
    seed = request.params.get("seed", request.seed)
    cv = int(request.params.get("cv", 10))
    standardize = request.params.get("standardize", True)
    alphas = request.params.get("alphas", None)
    is_classifier = len(np.unique(y)) <= 10 and y.dtype != float
    # 无留出集，全数据标准化不算泄漏，保留原逻辑
    if standardize:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        X_scaled = pd.DataFrame(X_scaled, columns=X.columns, index=X.index)
    else:
        X_scaled = X
    if alphas is None:
        alphas = np.logspace(-4, 1, 100)
    if is_classifier:
        model = LogisticRegressionCV(Cs=alphas, cv=cv, penalty='l1', solver='saga',
                                      random_state=seed, max_iter=5000, n_jobs=-1)
    else:
        model = LassoCV(alphas=alphas, cv=cv, random_state=seed, max_iter=5000, n_jobs=-1)
    model.fit(X_scaled, y)
    if is_classifier:
        best_alpha = 1.0 / model.C_[0]
        final_model = LogisticRegression(C=model.C_[0], penalty='l1', solver='saga',
                                          random_state=seed, max_iter=5000)
    else:
        best_alpha = model.alpha_
        final_model = Lasso(alpha=best_alpha, random_state=seed, max_iter=5000)
    final_model.fit(X_scaled, y)
    coefs = final_model.coef_
    if is_classifier and coefs.ndim > 1:
        coefs = coefs[0]
    coef_df = pd.DataFrame({
        "Variable": X.columns,
        "Coefficient": coefs,
        "AbsCoefficient": np.abs(coefs),
        "Selected": np.abs(coefs) > 1e-6
    }).sort_values("AbsCoefficient", ascending=False)
    # Charts
    fig, ax1 = plt.subplots(figsize=(8, 6))
    selected = coef_df[coef_df["Selected"]].sort_values("Coefficient")
    colors = ["#2ecc71" if c > 0 else "#e74c3c" for c in selected["Coefficient"]]
    ax1.barh(selected["Variable"], selected["Coefficient"], color=colors)
    ax1.set_xlabel("Coefficient")
    ax1.set_title(f"LASSO Coefficients (alpha={best_alpha:.4f})")
    chart1 = ChartData(title="LASSO回归系数", data=encode_figure(fig, fmt), type=fmt)
    path_chart = _plot_lasso_path(X_scaled, y, alphas, is_classifier, seed, fmt)
    cv_chart = _plot_lasso_cv(model, is_classifier, best_alpha, cv, fmt)
    charts = [chart1, path_chart, cv_chart]

    # Table
    table = TableData(
        title="LASSO系数表",
        headers=["Variable", "Coefficient", "Selected"],
        rows=coef_df[["Variable", "Coefficient", "Selected"]].values.tolist()
    )
    summary = f"LASSO回归完成。最优alpha={best_alpha:.4f}，共选择{coef_df['Selected'].sum()}个变量。"
    intercept_val = float(final_model.intercept_)
    if is_classifier and hasattr(final_model, 'intercept_') and np.ndim(final_model.intercept_) > 0:
        intercept_val = float(final_model.intercept_[0])
    model_info = {
        "model_type": "lasso",
        "coefficients": dict(zip(X.columns, coefs)),
        "intercept": intercept_val,
        "feature_names": list(X.columns),
        "alpha": best_alpha,
    }
    return {"charts": charts, "tables": [table], "summary": summary, "model_info": model_info}


def run_lasso_screening(request, fmt="svg"):
    result = run_lasso(request, fmt)
    result["summary"] = result["summary"].replace("LASSO回归完成", "LASSO特征筛选完成")
    if result.get("model_info"):
        result["model_info"]["model_type"] = "lasso-screening"
    return result


def run_lasso_predict(request, fmt="svg"):
    df = get_data_for_ml(
        request.dataset_id, request.y_variable, request.x_variables,
        request.is_survival, request.time_variable, request.filters
    )
    if len(df) == 0:
        raise ValueError("Filtered data is empty")
    X_df = df[list(request.x_variables)]
    y, le = encode_y(df[request.y_variable], request.variable_types)
    seed = request.params.get("seed", request.seed)
    test_size = request.params.get("testSize", 0.3)
    alpha = request.params.get("alpha", None)
    standardize = request.params.get("standardize", True)
    is_classifier = len(np.unique(y)) <= 10 and y.dtype != float
    if alpha is None:
        # 先用同参数划分（seed/test_size/stratify 相同，split 结果一致）在训练折内做 CV 选 alpha，
        # 预处理只在训练集 fit，避免泄漏
        if is_classifier:
            cv_model = LogisticRegressionCV(cv=5, penalty='l1', solver='saga', random_state=seed, max_iter=5000, n_jobs=-1)
        else:
            cv_model = LassoCV(cv=5, random_state=seed, max_iter=5000, n_jobs=-1)
        cv_pipe, _, _, _, _ = train_test_pipeline(
            cv_model, scale=standardize, X=X_df, y=y, test_size=test_size, seed=seed,
            stratify=is_classifier, variable_types=request.variable_types)
        cv_fitted = cv_pipe.named_steps["clf"]
        if is_classifier:
            alpha = 1.0 / cv_fitted.C_[0]
            model = LogisticRegression(C=cv_fitted.C_[0], penalty='l1', solver='saga', random_state=seed, max_iter=5000)
        else:
            alpha = cv_fitted.alpha_
            model = Lasso(alpha=alpha, random_state=seed, max_iter=5000)
    else:
        if is_classifier:
            model = LogisticRegression(C=1.0/alpha, penalty='l1', solver='saga', random_state=seed, max_iter=5000)
        else:
            model = Lasso(alpha=alpha, random_state=seed, max_iter=5000)
    pipe, X_train, X_test, y_train, y_test = train_test_pipeline(
        model, scale=standardize, X=X_df, y=y, test_size=test_size, seed=seed,
        stratify=is_classifier, variable_types=request.variable_types)
    feature_names = list(pipe.named_steps["prep"].get_feature_names_out())
    fitted = pipe.named_steps["clf"]
    y_pred = pipe.predict(X_test)
    if is_classifier and hasattr(pipe, "predict_proba"):
        y_prob = pipe.predict_proba(X_test)
        metrics = classification_metrics(y_test, y_pred, y_prob)
    else:
        metrics = regression_metrics(y_test, y_pred)
    coefs = fitted.coef_
    if is_classifier and coefs.ndim > 1:
        coefs = coefs[0]
    coef_df = pd.DataFrame({
        "Variable": feature_names,
        "Coefficient": coefs
    }).sort_values("Coefficient", key=lambda x: abs(x), ascending=False)
    fig, ax = plt.subplots(figsize=(8, max(5, len(coef_df)*0.3)))
    colors = ["#2ecc71" if c > 0 else "#e74c3c" for c in coef_df["Coefficient"]]
    ax.barh(coef_df["Variable"][::-1], coef_df["Coefficient"][::-1], color=colors[::-1])
    ax.set_title(f"Lasso Prediction Model (alpha={alpha:.4f})")
    chart1 = ChartData(title="预测模型系数", data=encode_figure(fig, fmt), type=fmt)
    metrics_table = TableData(
        title="模型评估指标",
        headers=["Metric", "Value"],
        rows=[[k, v] for k, v in metrics.items()]
    )
    n_train = len(y_train)
    n_test = len(y_test)
    summary = f"Lasso预测模型完成。训练集{n_train}，测试集{n_test}。"
    intercept_val = float(fitted.intercept_)
    if is_classifier and hasattr(fitted, 'intercept_') and np.ndim(fitted.intercept_) > 0:
        intercept_val = float(fitted.intercept_[0])
    model_info = {
        "model_type": "lasso-predict",
        "coefficients": dict(zip(feature_names, coefs)),
        "intercept": intercept_val,
        "feature_names": feature_names,
        "alpha": alpha,
    }
    return {"charts": [chart1], "tables": [metrics_table, TableData(title="系数表", headers=["Variable","Coefficient"], rows=coef_df.values.tolist())], "summary": summary, "model_info": model_info}
