from datetime import datetime
import os
import requests
import yaml
import pyodbc
import csv
from loguru import logger # type: ignore

class EbayManager:
    def __init__(self, config):
        self.config = config
        self._setup_logging()
        self.session = requests.Session()
        
    def _setup_logging(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_base = self.config['settings']['log_file']
        name, ext = os.path.splitext(log_base)
        unique_log_file = f"{name}_{timestamp}{ext}"
        logger.add(unique_log_file, rotation="10 MB", level=self.config['settings'].get('log_level', 'DEBUG'))
        
    def _get_headers(self):
        """Constructs the mandatory eBay headers."""
        headers = {
        "X-EBAY-API-CALL-NAME": "ReviseInventoryStatus",
        "X-EBAY-API-SITEID": self.config['ebay_api']['site_id'],
        "X-EBAY-API-COMPATIBILITY-LEVEL": self.config['ebay_api']['compatibility_level'],
        "Content-Type": "application/xml",
        "X-EBAY-API-APP-NAME": self.config['ebay_api']['credentials']['app_name'],
        "X-EBAY-API-DEV-NAME": self.config['ebay_api']['credentials']['dev_name'],
        "X-EBAY-API-CERT-NAME": self.config['ebay_api']['credentials']['cert_name']
        }     
        return headers
    
    def _build_stock_payload(self, batch):
        """Constructs the XML payload for a batch of items."""
        inventory_nodes = ""
        for item in batch:
            sku = item.get('sku', '')
            
            inventory_nodes += f"<InventoryStatus><ItemID>{item['item_id']}</ItemID>"
            if sku:
                inventory_nodes += f"<SKU>{sku}</SKU>"
            inventory_nodes += f"<Quantity>{item['stock']}</Quantity></InventoryStatus>"
        
        return f"""<?xml version="1.0" encoding="utf-8"?>
        <ReviseInventoryStatusRequest xmlns="urn:ebay:apis:eBLBaseComponents">
            <RequesterCredentials>
                <eBayAuthToken>{self.config['ebay_api']['token']}</eBayAuthToken>
            </RequesterCredentials>
            {inventory_nodes}
        </ReviseInventoryStatusRequest>"""
        
    def update_inventory(self, batch, session):
        """Sends the XML request and logs the result."""
        payload = self._build_stock_payload(batch)
        headers = self._get_headers()

        try:
            response = session.post(self.config['ebay_api']['endpoint'], data=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Simple check for success in XML response
            if "<Ack>Success</Ack>" in response.text or "<Ack>Warning</Ack>" in response.text:
                logger.info(f"Successfully processed batch of {len(batch)} items.")
                logger.debug(f"Update item {batch[0]['item_id']} with SKU: {batch[0]['sku']} with quantity: {batch[0]['stock']}")
                return True, {batch[0]['sku']}
            else:
                logger.error(f"eBay returned errors for item {batch[0]['sku']}: {response.text}")
                return False, {batch[0]['sku']}
                
        except Exception as e:
            logger.exception(f"Failed to send batch: {e}")
            
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
        """Closes the network session."""
        self.session.close()