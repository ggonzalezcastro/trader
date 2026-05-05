# FxGerardClient.mq5 - EA Thin Client

EA que conecta a un host Python por socket TCP, recibe comandos JSON y envia ticks.

## Configuracion en MT5

### 1. Allow WebRequest

El EA usa sockets TCP, no WebRequest, pero si MT5 bloquee sockets:

- Ir a `Herramientas > Opciones > Expert Advisors`
- Marcar `Allow DLL imports`
- Marcar `Allow WebRequest`

### 2. Configuracion del EA

| Parametro         | Valor por defecto | Descripcion                          |
|-------------------|-------------------|--------------------------------------|
| HostIP            | 127.0.0.1         | IP del host Python                   |
| HostPort          | 5555              | Puerto TCP del host                  |
| DefaultMagic      | 50001             | Magic number por defecto             |
| ReconnectMs       | 2000              | Intervalo de reconnect (ms)          |
| HeartbeatSec      | 5                 | Intervalo de heartbeat (segundos)    |
| LocalTrailing     | true              | Activa trailing stop local via ATR   |
| TrailATRmult      | 1.5               | Multiplicador ATR para trailing      |
| BreakevenAtR      | 0.5               | Breakeven ratio                      |

### 3. Protocolo JSON

**Tick enviado por EA:**

```json
{"type":"tick","seq":1,"sym":"EURUSD","bid":1.08500,"ask":1.08510,"t":1700000000}
```

**Comandos recibidos por EA:**

- `{"op":"open","symbol":"EURUSD","side":"buy","volume":0.1,"sl":1.080,"tp":1.090,"magic":50001,"comment":"","req_id":1}`
- `{"op":"close","ticket":123456,"req_id":1}`
- `{"op":"modify","ticket":123456,"sl":1.082,"tp":1.092,"req_id":1}`
- `{"op":"close_all","magic":50001,"reason":"equity","req_id":1}`
- `{"op":"ping","req_id":1}`

**Ack enviado por EA:**

```json
{"type":"ack","req_id":1,"ok":true,"ticket":123456,"retcode":10009}
```