# Plan: Framework Trading Python + MQL5 (FxGerard)

**Generated**: 2026-05-05
**Status**: En ejecución

## Overview
Framework híbrido Python + MQL5 para trading automático. Núcleo Python con aiomql en VPS local/Linux, EA thin client MQL5 en Windows/MT5, comunicación TCP sockets JSONL. Objetivo: robots FxGerard A/B/C en M5/M15, compliance FTMO/FundedNext, paper→live→funded.

## Architecture

```
Local Machine (Windows VM + MT5)
├── MT5 Terminal #1 (Broker demo)
│   └── FxGerardClient.mq5 (EA thin)
└── Python Host (aiomql + Robot SDK)
    ├── core/
    │   ├── compliance.py
    │   ├── risk.py
    │   └── news.py
    └── robots/
        ├── fxgerard-vwap-reversal/  (A)
        ├── fxgerard-sweep-choch/     (B)
        └── fxgerard-bos-continuation/(C)

Railway (Linux containers)
├── Redis (state)
├── NATS (event bus)
└── FastAPI (dashboard API - opcional)
```

## Sprints

### Sprint 1: Proyecto base + Robot SDK
**Goal**: Proyecto Python funcional con Robot ABC y loader
**Demo**: `python -c "from robots import load_robot; r = load_robot(...)" print(r.name)`

### Sprint 2: Compliance engine
**Goal**: Módulo compliance.py con profiles FTMO/FundedNext
**Demo**: `pytest tests/test_compliance.py -v`

### Sprint 3: Estrategias FxGerard
**Goal**: FxGerard A/B/C codificados con tests
**Demo**: Backtest Sharpe > 0.8 OOS

### Sprint 4: EA thin client
**Goal**: FxGerardClient.mq5 con socket TCP
**Demo**: EA conecta a Python, recibe ticks, ejecuta orden

### Sprint 5: Docker + servicios
**Goal**: docker-compose.yml con Redis + NATS + API
**Demo**: `docker-compose up -d` levanta todos los servicios

## Tech Stack

| Componente | Librería |
|---|---|
| Python MT5 | `MetaTrader5==5.0.5735` |
| Async framework | `aiomql==4.1.2` |
| Types | `pydantic>=2.7` |
| SMC concepts | `smartmoneyconcepts` |
| Optimización | `optuna>=4.0`, `vectorbt` |
| Event bus | `nats-py` |
| State | `redis` |
| Backtest | `backtesting.py` |

## Brokers Soportados
- FTMO: 2000 req/day, $400K cap, 2min news blackout
- FundedNext: $300K cap, MT4/MT5 only

## Magics
- FxGerard A: 50001
- FxGerard B: 50002
- FxGerard C: 50003