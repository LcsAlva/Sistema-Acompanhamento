from fastapi import APIRouter
import urllib.request
import json
from datetime import datetime

router = APIRouter(prefix="/clima", tags=["clima"])

DIAS_PT = ['Seg','Ter','Qua','Qui','Sex','Sáb','Dom']

@router.get("")
@router.get("/")
def get_clima():
    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=-23.6678&longitude=-46.4614"
        "&daily=weathercode,temperature_2m_max,temperature_2m_min"
        "&timezone=America%2FSao_Paulo&forecast_days=7"
    )
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        dias = []
        for i, d in enumerate(data["daily"]["time"]):
            dt = datetime.strptime(d, "%Y-%m-%d")
            dias.append({
                "data": d,
                "data_fmt": dt.strftime("%d/%m"),
                "dia_semana": DIAS_PT[dt.weekday()],
                "weathercode": data["daily"]["weathercode"][i],
                "temp_max": data["daily"]["temperature_2m_max"][i],
                "temp_min": data["daily"]["temperature_2m_min"][i],
            })
        return dias
    except Exception as e:
        # Retorna lista com flag de erro para o frontend distinguir "sem dados" de "falha"
        return [{"erro": True, "mensagem": str(e)}]
