from locust import HttpUser, task, between
import random

class CreditScoringUser(HttpUser):
    # Várunk 1 és 3 másodperc között két kérés között
    wait_time = between(1, 3)

    @task
    def predict_credit_score(self):
        """
        Szimulál egy ügyintézőt, aki hitelkérelmeket küld be.
        Randomizáljuk az adatokat, hogy a gyorsítótárazás (caching) ne torzítsa a mérést.
        """
        
        payload = {
            "application_data": {
                # Randomizált bevételek 10M és 100M között
                "NetSales": random.uniform(10_000_000, 100_000_000),
                "Operating Margin": random.uniform(-10.0, 30.0),
                "Current Ratio": random.uniform(0.5, 3.0),
                "DebtToEquityRatio": random.uniform(0.1, 5.0),
                "Return on Assets (ROA)": random.uniform(-5.0, 15.0),
                "LatePaymentCount": random.randint(0, 5),
                "Industry_code": random.choice(["Építőipar", "IT", "Kereskedelem"]),
                "legal_entity_type": random.choice(["Kft.", "Zrt."]),
                "description": "Standard terhelési teszt kérés."
            }
        }
        
        # POST kérés az API-nak
        # Fontos: A Locust a 'host' paramétert parancssorból kapja
        with self.client.post("/scoring/predict", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Hiba: {response.status_code} - {response.text}")