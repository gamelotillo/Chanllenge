from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import List, Optional
import json
from datetime import datetime
import os
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import psycopg2  # Para DB

app = FastAPI(title="System Info API")

Base = declarative_base()

class SystemInfo(BaseModel):
    ip: str
    cpu: dict
    processes: List[dict]
    users: List[dict]
    os: dict
    timestamp: str

class DBSystemInfo(Base):
    __tablename__ = "system_info"
    id = Column(Integer, primary_key=True)
    ip = Column(String(45))
    cpu_json = Column(Text)
    processes_json = Column(Text)
    users_json = Column(Text)
    os_json = Column(Text)
    timestamp = Column(DateTime)

# Config DB si se usa
DB_URL = os.getenv('DB_URL')  # e.g., postgresql://user:pass@host/db
engine = create_engine(DB_URL) if DB_URL else None
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None
Base.metadata.create_all(bind=engine) if engine else None

@app.post("/send")
async def receive_info(info: SystemInfo):
    timestamp_str = info.timestamp.replace(":", "-")  # Para nombre archivo seguro
    filename = f"system_data_{timestamp_str}.json"
    
    # Almacenar en JSON
    data_entry = info.dict()
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                existing = json.load(f)
            existing.append(data_entry)
            with open(filename, 'w') as f:
                json.dump(existing, f, indent=2)
        else:
            with open(filename, 'w') as f:
                json.dump([data_entry], f, indent=2)
    except Exception as e:
        return {"error": f"Error guardando JSON: {e}"}
    
    # Si DB configurada, almacenar en DB
    if SessionLocal:
        db = SessionLocal()
        db_info = DBSystemInfo(
            ip=info.ip,
            cpu_json=json.dumps(info.cpu),
            processes_json=json.dumps(info.processes),
            users_json=json.dumps(info.users),
            os_json=json.dumps(info.os),
            timestamp=datetime.fromisoformat(info.timestamp)
        )
        db.add(db_info)
        db.commit()
        db.close()
    
    return {"status": "success", "filename": filename}

@app.get("/query")
async def query_info(ip: str = Query(..., description="IP a consultar")):
    results = []
    # Buscar en todos los JSON
    for file in os.listdir('.'):
        if file.startswith("system_data_") and file.endswith(".json"):
            with open(file, 'r') as f:
                data = json.load(f)
                for entry in data:
                    if entry['ip'] == ip:
                        results.append(entry)
    
    # Si DB, query DB
    if SessionLocal:
        db = SessionLocal()
        db_results = db.query(DBSystemInfo).filter(DBSystemInfo.ip == ip).all()
        for res in db_results:
            results.append({
                'ip': res.ip,
                'cpu': json.loads(res.cpu_json),
                'processes': json.loads(res.processes_json),
                'users': json.loads(res.users_json),
                'os': json.loads(res.os_json),
                'timestamp': res.timestamp.isoformat()
            })
        db.close()
    
    return {"results": results}