SELECT  
	E.item_id as item_id, 
	E.sku as sku,
	CASE 
		WHEN (S.StockOnHand - S.StockCommitted) < 0 THEN 0
		ELSE CAST((S.StockOnHand - S.StockCommitted) AS INT) 
	END AS stock
FROM
[dbo].[boating_items] AS E
LEFT JOIN[dbo].[CC_Stock] AS S ON E.sku = S.SKU
WHERE E.sku != ''   AND StockOnHand is not null