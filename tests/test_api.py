import pytest
import json
from app import app # Importáljuk a Flask alkalmazásunkat

# --- Teszt Kliens Beállítása ---
@pytest.fixture
def client():
    """Létrehoz egy teszt klienst a Flask alkalmazáshoz."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

# --- 1. Pozitív Teszt: Helyes Hitelbírálati Kérés ---
def test_predict_success(client):
    """Teszteli a sikeres hitelbírálati kérést helyes adatokkal."""
    
    valid_payload = {
        "application_data": {
            "NetSales": 50000000,
            "Operating Margin": 12.5,
            "Current Ratio": 1.5,
            "DebtToEquityRatio": 2.1,
            "Return on Assets (ROA)": 5.4,
            "LatePaymentCount": 0,
            "Industry_code": "Építőipar",
            "legal_entity_type": "Kft.",
            "description": "Stabil, megbízható ügyfél."
        }
    }
    
    response = client.post('/scoring/predict', 
                           data=json.dumps(valid_payload),
                           content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    
    # Ellenőrizzük, hogy a válasz tartalmazza-e a kulcsmezőket
    assert 'status' in data
    assert data['status'] == 'success'
    assert 'prediction' in data
    assert 'probability_of_default' in data
    assert 'shadow_metadata' in data
    
    # NLP Bias ellenőrzés: Mivel a szöveg pozitív és a cég jó, nem lehet bias
    assert data['shadow_metadata']['sentiment_score'] > 0

# --- 2. Negatív Teszt: Hiányzó Adatok ---
def test_predict_missing_data(client):
    """Teszteli az API viselkedését, ha a 'application_data' hiányzik."""
    
    invalid_payload = {
        "wrong_key": "some_data"
    }
    
    response = client.post('/scoring/predict', 
                           data=json.dumps(invalid_payload),
                           content_type='application/json')
    
    # A Swagger validáció miatt 400 Bad Request-et várunk
    assert response.status_code == 400

# --- 3. Negatív Teszt: Hibás Adattípus ---
def test_predict_invalid_data_type(client):
    """Teszteli az API viselkedését helytelen adattípusok esetén."""
    
    invalid_payload = {
        "application_data": {
            "NetSales": "nagyon_sok_penz", # Szöveg a szám helyett!
            "Operating Margin": 12.5,
            # ... többi mező kihagyva az egyszerűség kedvéért
        }
    }
    
    response = client.post('/scoring/predict', 
                           data=json.dumps(invalid_payload),
                           content_type='application/json')
    
    # A Swagger/Flask-RESTX ezt is megfogja
    assert response.status_code == 400