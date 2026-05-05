# Trading Framework

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

### Paper Trading
```bash
python -m core.host
```

### Live Trading
```bash
python -m core.host --live
```

## Estructura

```
trading/
├── core/           # Host principal, compliance, risk, news
├── robots/         # Robot loader
├── tests/          # Tests
└── scripts/        # Scripts auxiliares
```
