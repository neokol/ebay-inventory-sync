from datetime import datetime
import json
import os
import requests
import yaml
import pyodbc
import csv
from loguru import logger # type: ignore

class AmazonInventoryManager:
    def __init__(self, config):
        self.config = config
        self._setup_logging()
        self.session = requests.Session()
        self.api_cfg = self.config['amazon_api']
        self.current_access_token = None
    
    def _setup_logging(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_base = self.config['settings']['log_file']
        name, ext = os.path.splitext(log_base)
        unique_log_file = f"{name}_{timestamp}{ext}"
        logger.add(unique_log_file, rotation="10 MB", level=self.config['settings'].get('log_level', 'DEBUG'))
    
    def _refresh_access_token(self):
        """Exchange Refresh Token for a temporary Access Token."""
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.api_cfg['refresh_token'],
            "client_id": self.api_cfg['client_id'],
            "client_secret": self.api_cfg['client_secret']
        }
        
        try:
            logger.info("Requesting new Amazon Access Token...")
            response = self.session.post(self.api_cfg['lwa_endpoint'], data=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
            self.current_access_token = data['access_token']
            logger.info("Amazon Access Token refreshed successfully.")
        except Exception as e:
            logger.error(f"Failed to refresh Amazon token: {e}")
            raise RuntimeError("Cannot proceed without valid Amazon Access Token.")

    def _get_headers(self):
        """Constructs the mandatory Amazon SP-API headers."""
        return {
            "x-amz-access-token": self.current_access_token,
            "Content-Type": "application/json"
        }

    def _build_payload(self, stock):
        """Generates the JSON patch payload for Amazon SP-API."""
        return json.dumps({
            "productType": "PRODUCT",
            "patches": [
                {
                    "op": "replace",
                    "path": "/attributes/fulfillment_availability",
                    "value": [
                        {
                            "fulfillment_channel_code": "DEFAULT",
                            "quantity": int(stock)
                        }
                    ]
                }
            ]
        })
    
    def _build_price_payload(self, price, currency):
        """Generates the JSON patch price payload for Amazon SP-API."""
        return json.dumps({
            "productType": "PRODUCT",
            "patches": [
                {
                    "op": "replace",
                    "path": "/attributes/purchasable_offer",
                    "value": [
                        {
                            "currency": currency,
                            "our_price": [
                                {
                                    "schedule": [
                                        {
                                            "value_with_tax": float(price)
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        })
    
    def _build_stock_price_payload(self, stock, price, currency):
        """Generates a combined JSON patch for stock and price."""
        return json.dumps({
            "productType": "PRODUCT",
            "patches": [
                {
                    "op": "replace",
                    "path": "/attributes/fulfillment_availability",
                    "value": [
                        {
                            "fulfillment_channel_code": "DEFAULT",
                            "quantity": int(stock)
                        }
                    ]
                },
                {
                    "op": "replace",
                    "path": "/attributes/purchasable_offer",
                    "value": [
                        {
                            "currency": currency,
                            "our_price": [
                                {
                                    "schedule": [
                                        {
                                            "value_with_tax": float(price)
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        })

    def update_inventory(self, batch, session):
        """Sends the request to Amazon and returns status + SKU."""
        
        if not self.current_access_token:
            self._refresh_access_token()
        
        item = batch[0]
        sku = str(item.get('sku', '')).strip()
        stock = item.get('stock', 0)
        price = item.get('price', 0)
        currency = item.get('currency', 'USD')

        if not sku:
            logger.error("Amazon requires a SKU. Skipping empty SKU.")
            return False, "N/A"

        url = f"{self.api_cfg['base_url']}/listings/2021-08-01/items/{self.api_cfg['seller_id']}/{sku}?marketplaceIds={self.api_cfg['marketplace_id']}"
        update_type = self.config['settings'].get('update_type', 'stock').lower()
        if update_type == 'stock':
            payload = self._build_payload(stock)
            log_msg = f"Stock: {stock}"
        elif update_type == 'price':
            payload = self._build_price_payload(price, currency)
            log_msg = f"Price: {price} {currency}"
        elif update_type == 'stock_price':
            payload = self._build_stock_price_payload(stock, price, currency)
            log_msg = f"Stock: {stock}, Price: {price} {currency}"
        headers = self._get_headers()

        try:
            response = session.patch(url, data=payload, headers=headers, timeout=30)
            
            
            if response.status_code in [401, 403]:
                logger.warning("Token expired during update. Refreshing...")
                self._refresh_access_token()
                response = session.patch(url, data=payload, headers=self._get_headers(), timeout=30)
            
            response.raise_for_status()
            
            # SP-API returns 200 OK or 202 Accepted for successful patches
            if response.status_code in [200, 202]:
                logger.info(f"AMAZON SUCCESS: SKU {sku} | {log_msg}")
                return True, sku
            else:
                logger.error(f"AMAZON ERROR for SKU {sku}: {response.text}")
                return False, sku
                
        except Exception as e:
            logger.error(f"Amazon Network/System error for SKU {sku}: {e}")
            return False, sku
        
    def fetch_data(self):
        """Determines where to get data based on config."""
        mode = self.config['settings'].get('mode', 'file')
        
        if mode == 'file':
            return self._read_from_csv()
        elif mode == 'database':
            return self._read_from_sql()
        else:
            raise ValueError(f"Unknown mode: {mode}")
    
    def _read_from_sql(self):
        try:
            db_cfg = self.config['database']
            query_path = self.config['settings']['query_file']
            
            # Load SQL query from external file
            with open(query_path, 'r') as f:
                sql_query = f.read()

            conn_str = (
                f"DRIVER={db_cfg['driver']};"
                f"SERVER={db_cfg['server']};"
                f"DATABASE={db_cfg['database']};"
                f"UID={db_cfg['username']};"
                f"PWD={db_cfg['password']}"
            )

            logger.info(f"Connecting to SQL Server: {db_cfg['server']}")
            with pyodbc.connect(conn_str) as conn:
                cursor = conn.cursor()
                cursor.execute(sql_query)
                
                # Fetch all and convert to list of dicts to match CSV format
                columns = [column[0] for column in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.exception(f"Error reading from SQL database: {e}")
            return []
    
    def _read_from_csv(self):
        try:
            file_path = self.config['settings']['inventory_file']
            with open(file_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                reader.fieldnames = [name.strip() for name in reader.fieldnames]
                items = [row for row in reader]
                return items
        except Exception as e:
            logger.exception(f"Error reading from CSV file: {e}")
            return []
    
    def close(self):
        """Closes the Amazon network session."""
        self.session.close()