# Trading Signal Server - API Documentation 
Version 2.0 | Last Updated: December 2024 
 
## Quick Start 
- Server Type: TCP Socket Server (JSON over TCP) 
- Default Port: 9999 
- Authentication: Password-based per client type 
 
## Admin Client API 
### 1. Send Trading Signal 
Request: 
```json 
{ 
  "client_type": "admin", 
  "password": "admin123", 
  "action": "send_signal", 
  "symbol": "BTCUSD", 
  "price": 50000.0, 
  "sl": 49500.0, 
  "tp": 51000.0, 
  "type": "buy" 
} 
``` 
