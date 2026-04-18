"""FastAPI application entry point for medical indicator standardization API."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import analysis, exam, patient

app = FastAPI(
    title="医疗体检指标标准化 API",
    description="HIS 体检指标名称标准化系统 — 客户查询、指标对比、四象限分析、疗效预测",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(exam.router)
app.include_router(patient.router)
app.include_router(analysis.router)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}
