# eBay Inventory Sync Tool

A professional Python-based utility designed to synchronize inventory levels from local data sources (CSV) or SQL Server databases to eBay listings using the eBay Trading API (XML).

## Features

- **Dual Mode Operation**: Support for reading inventory from local `.csv` files or direct SQL Server queries.
- **Asynchronous Execution**: Uses persistent HTTP sessions (`requests.Session`) for optimized performance.
- **Robust Logging**: Integrated with `loguru` for detailed, timestamped logging and rotation.
- **Secure Configuration**: Externalized credentials and settings via `config.yaml`.
- **Fault Tolerant**: Handles single-item vs. multi-variation (SKU) eBay listing logic automatically.

## Prerequisites

- **eBay Developer Account**: Requires AppID, DevID, CertID, and a User Auth Token.
- **ODBC Driver**: For database mode, ensure 'ODBC Driver 17 for SQL Server' is installed on the host machine.
- **Python Environment**: Managed via `uv` for high-performance dependency resolution.

## Installation

1. Clone or copy the project directory to your machine.
2. Ensure you have `uv` installed.
3. Synchronize dependencies: 
    ```bash
    uv sync

### Configuration
The tool relies on config.yaml for all environment-specific settings.
Key Sections:
ebay_api: Contains your API endpoint, tokens, and site credentials.

Important: When entering SQL Server instances (e.g., SERVER\INSTANCE), use single quotes in the YAML file to prevent escape character errors: server: 'NAME\INSTANCE'.

#### Settings:

- mode: Set to "file" for CSV or "database" for SQL.

- inventory_file: Path to your CSV.

- query_file: Path to your .sql query file.

- database: Credentials for your SQL Server instance (Server, Database, UID, PWD).

#### Data Schema
The tool expects three specific data points regardless of the source:

item_id: The eBay Item ID (Listing ID).

sku: The variation SKU (required for multi-variation listings; leave empty for single items).

stock: The absolute quantity to be set on eBay.

CSV Example:
```
item_id,sku,stock
251802096274,PROD-123-RED,50
263879278302,MA 001,15
```

SQL Example: 
```
SELECT eBayID as item_id, SKUCode as sku, CurrentQty as stock 
FROM InventoryTable
```

### Usage
1. Running via Source
    Execute the tool using uv: ```uv run main.py```

2. Building the Executable
    To create a standalone .exe for Windows: ```uv run pyinstaller --onefile --name "EbayStockSync" main.py```
    The resulting file will be in the dist/ folder.

### Logging
Logs are generated with the format ebay_sync_YYYYMMDD_HHMMSS.log.

- INFO: General progress and success messages.
- DEBUG: Specific item details and payload tracking.
- ERROR: eBay API rejections or network failures.

## Directory Structure
.
├── main.py              # Entry point
├── config.yaml          # Configuration (Tokens, DB settings)
├── query.sql            # Your SQL logic
├── inventory.csv        # Local data source (if in file mode)
└── dist/                # Created after build
    └── EbayStockSync.exe