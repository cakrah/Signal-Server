# Admin API Documentation 
## Authentication 
- Client Type: "admin" 
- Password: "admin123" 
 
## 1. Send Trading Signal 
\`\`\`json 
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
\`\`\` 
