# -*- coding: utf-8 -*-
"""统一模型注册表：前端短 key（"XGB"）与向导长 key（"random-forest"）都映射到同一实现。

修复 REPAIR_LOG #3：bestModel 格式不一致 —— 此后所有入口统一经 create_model() 实例化。
"""
from __future__ import annotations

import os

# key 归一化：全部转到 compare 用的短标签
ALIASES = {
    "lr": "LR", "logistic": "LR", "logistic-regression": "LR",
    "dt": "DT", "decision-tree": "DT",
    "rf": "RF", "random-forest": "RF",
    "svm": "SVM",
    "knn": "KNN",
    "gbdt": "GBDT", "gradient-boosting": "GBDT",
    "xgb": "XGB", "xgboost": "XGB",
    "lgbm": "LGBM", "lightgbm": "LGBM",
    "lda": "LDA", "qda": "QDA",
    "mlp": "MLP",
    "nb": "NB", "naive-bayes": "NB",
    "catboost": "CatBoost",
    "tabpfn": "TabPFN",
    "lasso": "Lasso", "lasso-predict": "Lasso",
    "elastic-net": "ENet", "elasticnet": "ENet",
}

# 需要标准化的模型
NEEDS_SCALE = {"LR", "SVM", "KNN", "MLP", "LDA", "QDA", "NB", "Lasso", "ENet"}

COMPARE_DEFAULTS = ["LR", "DT", "RF", "SVM", "KNN", "GBDT"]


def canonical_key(model_type: str) -> str:
    key = ALIASES.get(str(model_type).strip().lower())
    if key is None:
        raise ValueError(f"不支持的模型类型: {model_type}")
    return key


def needs_scale(model_type: str) -> bool:
    return canonical_key(model_type) in NEEDS_SCALE


def create_model(model_type: str, params: dict | None = None, seed: int = 123):
    """按统一 key 实例化模型；params 支持前端向导传入的参数名。"""
    key = canonical_key(model_type)
    p = params or {}

    if key == "LR":
        from sklearn.linear_model import LogisticRegression
        return LogisticRegression(C=float(p.get("C", 1.0)), max_iter=3000, random_state=seed, n_jobs=-1)
    if key == "Lasso":
        from sklearn.linear_model import LogisticRegression
        return LogisticRegression(penalty="l1", solver="liblinear", C=float(p.get("C", 0.5)), max_iter=3000, random_state=seed)
    if key == "ENet":
        from sklearn.linear_model import LogisticRegression
        return LogisticRegression(penalty="elasticnet", solver="saga", C=float(p.get("C", 0.5)),
                                  l1_ratio=float(p.get("l1Ratio", 0.5)), max_iter=5000, random_state=seed)
    if key == "DT":
        from sklearn.tree import DecisionTreeClassifier
        return DecisionTreeClassifier(max_depth=int(p.get("maxDepth", 8)), min_samples_leaf=int(p.get("minSamplesLeaf", 1)),
                                      random_state=seed)
    if key == "RF":
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(n_estimators=int(p.get("nEstimators", 200)), max_depth=int(p.get("maxDepth", 10)),
                                      min_samples_leaf=int(p.get("minSamplesLeaf", 1)), random_state=seed, n_jobs=-1)
    if key == "GBDT":
        from sklearn.ensemble import GradientBoostingClassifier
        return GradientBoostingClassifier(n_estimators=int(p.get("nEstimators", 200)),
                                          learning_rate=float(p.get("learningRate", 0.1)), random_state=seed)
    if key == "SVM":
        from sklearn.svm import SVC
        return SVC(kernel=p.get("kernel", "rbf"), C=float(p.get("C", 1.0)), gamma=p.get("gamma", "scale"),
                   probability=True, random_state=seed)
    if key == "KNN":
        from sklearn.neighbors import KNeighborsClassifier
        return KNeighborsClassifier(n_neighbors=int(p.get("k", 5)), weights=p.get("weights", "uniform"))
    if key == "LDA":
        from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
        return LinearDiscriminantAnalysis(solver=p.get("solver", "lsqr"), shrinkage="auto" if p.get("solver", "lsqr") == "lsqr" else None)
    if key == "QDA":
        from sklearn.discriminant_analysis import QuadraticDiscriminantAnalysis
        return QuadraticDiscriminantAnalysis(reg_param=float(p.get("regParam", 0.1)))
    if key == "NB":
        from sklearn.naive_bayes import GaussianNB
        return GaussianNB(var_smoothing=float(p.get("varSmoothing", 1e-9)))
    if key == "MLP":
        from sklearn.neural_network import MLPClassifier
        hidden = p.get("hiddenLayers", "100,50")
        hidden = tuple(int(x) for x in str(hidden).split(",") if x.strip())
        return MLPClassifier(hidden_layer_sizes=hidden, alpha=float(p.get("alpha", 1e-4)),
                             max_iter=int(p.get("maxIter", 1000)), early_stopping=True, random_state=seed)
    if key == "XGB":
        from xgboost import XGBClassifier
        return XGBClassifier(n_estimators=int(p.get("nEstimators", 200)), max_depth=int(p.get("maxDepth", 5)),
                             learning_rate=float(p.get("learningRate", 0.1)), subsample=float(p.get("subsample", 0.8)),
                             random_state=seed, n_jobs=-1, eval_metric="logloss")
    if key == "LGBM":
        from lightgbm import LGBMClassifier
        return LGBMClassifier(n_estimators=int(p.get("nEstimators", 200)), learning_rate=float(p.get("learningRate", 0.1)),
                              num_leaves=int(p.get("numLeaves", 31)), random_state=seed, n_jobs=-1, verbosity=-1)
    if key == "CatBoost":
        from catboost import CatBoostClassifier
        return CatBoostClassifier(iterations=int(p.get("iterations", 300)), learning_rate=float(p.get("learningRate", 0.1)),
                                  depth=int(p.get("depth", 6)), random_seed=seed, verbose=0, allow_writing_files=False)
    if key == "TabPFN":
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        from tabpfn import TabPFNClassifier
        device = "cpu"
        try:
            import torch
            if torch.cuda.is_available():
                device = "cuda"
        except Exception:
            pass
        return TabPFNClassifier(n_estimators=int(p.get("nEstimators", 8)), device=device)
    raise ValueError(f"未实现的模型: {model_type}")


def available_models(keys) -> list[str]:
    """过滤出当前环境可实例化的模型 key。"""
    ok = []
    for k in keys:
        try:
            create_model(k)
            ok.append(k)
        except Exception:
            continue
    return ok
