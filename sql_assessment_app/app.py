import streamlit as st
import re
import pandas as pd
import os
import io
from datetime import datetime
import random
import hashlib
import pathlib

# ==========================
# Normalization function
# ==========================
def normalize_sql(sql):
    """Normalize SQL text for comparison: lowercase, remove extra spaces, sort SELECT columns."""
    sql = sql.lower().strip().rstrip(";")
    sql = re.sub(r"\s+", " ", sql)
    # Remove aliases: simple heuristic
    sql = re.sub(r"\bas\s+\w+", "", sql)
    sql = re.sub(r"\bfrom\s+(\w+)\s+\w+", r"from \1", sql)

    # Normalize SELECT column order
    if sql.startswith("select"):
        parts = sql.split("from")
        select_part = parts[0].replace("select", "").strip()
        rest = "from" + "from".join(parts[1:]) if len(parts) > 1 else ""
        columns = [c.strip() for c in select_part.split(",")]
        columns.sort()
        sql = "select " + ", ".join(columns) + " " + rest

    return sql


def parse_sample_text(sample_text):
    """Parse sample text into structured forms for rendering.

    Supported formats:
    - "input ? output" -> {'type': 'io', 'input': ..., 'output': ...}
    - "k: v, k2: v2" -> {'type': 'kv', 'rows': [ {Column, Value}, ... ]}
    - fallback -> {'type': 'text', 'text': sample_text}
    """
    if not isinstance(sample_text, str):
        return {"type": "text", "text": str(sample_text)}

    if ' ? ' in sample_text:
        parts = sample_text.split(' ? ', 1)
        return {"type": "io", "input": parts[0].strip(), "output": parts[1].strip()}

    if ',' in sample_text and ':' in sample_text:
        pairs = [p.strip() for p in sample_text.split(',')]
        rows = []
        for pair in pairs:
            if ':' in pair:
                k, v = pair.split(':', 1)
                rows.append({"Column": k.strip(), "Value": v.strip()})
        if rows:
            return {"type": "kv", "rows": rows}

    return {"type": "text", "text": sample_text}

# ==========================
# SQL Question Bank with Enhanced Information
# ==========================
QUESTIONS = [
    {
        "id":1, 
        "question":"Which shippers do we have?", 
        "description": "Retrieve a list of all shipping companies (shippers) available in the database. This helps users identify every carrier that can be used for order deliveries, which is useful for logistics and supply chain analysis.",
        "tables": ["shippers"],
        "table_info": {
            "shippers": {
                "columns": ["shipperid (INT, PK)", "companyname (VARCHAR)", "phone (VARCHAR)"],
                "sample": "shipperid: 1, companyname: 'Speedy Express', phone: '(503) 555-9831'"
            }
        },
        "solution":"SELECT * FROM shippers"
    },
    {
        "id":2, 
        "question":"Certain fields from Categories", 
        "description": "Extract the name and description of each product category. This query helps users understand how products are grouped and categorized in the database, which is important for inventory management and reporting.",
        "tables": ["categories"],
        "table_info": {
            "categories": {
                "columns": ["categoryid (INT, PK)", "categoryname (VARCHAR)", "description (TEXT)"],
                "sample": "categoryid: 1, categoryname: 'Beverages', description: 'Soft drinks, coffees, teas...'"
            }
        },
        "solution":"SELECT categoryname, description FROM categories"
    },
    {
        "id":3, 
        "question":"Sales Representatives", 
        "description": "List all employees whose job title is 'Sales Representative'. Display their names and hire dates to track the composition and tenure of the sales team, which is useful for HR and sales management.",
        "tables": ["employees"],
        "table_info": {
            "employees": {
                "columns": ["employeeid (INT, PK)", "firstname (VARCHAR)", "lastname (VARCHAR)", "title (VARCHAR)", "hiredate (DATE)"],
                "sample": "employeeid: 1, firstname: 'Nancy', lastname: 'Davolio', title: 'Sales Representative', hiredate: '1992-05-01'"
            }
        },
        "solution":"SELECT firstname, lastname, hiredate FROM employees WHERE title = 'Sales Representative'"
    },
    {
        "id":4, 
        "question":"Sales Representatives in the United States", 
        "description": "Filter the list of sales representatives to show only those based in the United States. This helps regional managers focus on the US sales team for performance reviews or territory planning.",
        "tables": ["employees"],
        "table_info": {
            "employees": {
                "columns": ["employeeid (INT, PK)", "firstname (VARCHAR)", "lastname (VARCHAR)", "title (VARCHAR)", "country (VARCHAR)", "hiredate (DATE)"],
                "sample": "employeeid: 1, firstname: 'Nancy', lastname: 'Davolio', title: 'Sales Representative', country: 'USA', hiredate: '1992-05-01'"
            }
        },
        "solution":"SELECT firstname, lastname, hiredate FROM employees WHERE title = 'Sales Representative' AND country = 'USA'"
    },
    {
        "id":5, 
        "question":"Orders placed by specific EmployeeID", 
        "description": "Retrieve all orders that were handled by the employee with EmployeeID 5. This query is useful for tracking the sales performance and order history of a specific employee, such as for performance reviews or commission calculations.",
        "tables": ["orders"],
        "table_info": {
            "orders": {
                "columns": ["orderid (INT, PK)", "customerid (VARCHAR, FK)", "employeeid (INT, FK)", "orderdate (DATE)", "shipcountry (VARCHAR)"],
                "sample": "orderid: 10248, customerid: 'VINET', employeeid: 5, orderdate: '1996-07-04', shipcountry: 'France'"
            }
        },
        "solution":"SELECT * FROM orders WHERE employeeid = '5'"
    },
    {
        "id":6, 
        "question":"Suppliers and ContactTitles", 
        "description": "Find all suppliers, excluding those whose contact title is 'Marketing Manager'. This helps identify key decision makers and procurement contacts at supplier organizations, which is important for business-to-business communications.",
        "tables": ["suppliers"],
        "table_info": {
            "suppliers": {
                "columns": ["supplierid (INT, PK)", "companyname (VARCHAR)", "contactname (VARCHAR)", "contacttitle (VARCHAR)"],
                "sample": "supplierid: 1, companyname: 'Exotic Liquids', contactname: 'Charlotte Cooper', contacttitle: 'Purchasing Manager'"
            }
        },
        "solution":"SELECT supplierid, contactname, contacttitle FROM suppliers WHERE contacttitle <> 'Marketing Manager'"
    },
    {
        "id":7, 
        "question":"Products with queso in ProductName", 
        "description": "Search for all products whose names contain the word 'queso'. This demonstrates the use of pattern matching (LIKE operator) for product discovery, which is useful for inventory management and marketing analysis.",
        "tables": ["products"],
        "table_info": {
            "products": {
                "columns": ["productid (INT, PK)", "productname (VARCHAR)", "categoryid (INT, FK)", "unitprice (DECIMAL)"],
                "sample": "productid: 11, productname: 'Queso Cabrales', categoryid: 4, unitprice: 21.00"
            }
        },
        "solution":"SELECT productid, productname FROM products WHERE productname LIKE '%queso%'"
    },
    {
        "id":8, 
        "question":"Orders shipping to France or Belgium", 
        "description": "Find all orders that are being shipped to either France or Belgium. This query is useful for regional shipping analysis, logistics planning, and understanding demand in specific European markets.",
        "tables": ["orders"],
        "table_info": {
            "orders": {
                "columns": ["orderid (INT, PK)", "customerid (VARCHAR, FK)", "shipcountry (VARCHAR)", "shippeddate (DATE)"],
                "sample": "orderid: 10248, customerid: 'VINET', shipcountry: 'France', shippeddate: '1996-07-10'"
            }
        },
        "solution":"SELECT orderid, customerid, shipcountry FROM orders WHERE shipcountry = 'France' OR shipcountry = 'Belgium'"
    },
    {
        "id":9, 
        "question":"Orders shipping to any country in Latin America", 
        "description": "Filter orders to show only those shipped to countries in Latin America (Brazil, Mexico, Argentina, Venezuela). Demonstrates the use of the IN clause for grouping multiple conditions, which is useful for regional sales and logistics analysis.",
        "tables": ["orders"],
        "table_info": {
            "orders": {
                "columns": ["orderid (INT, PK)", "customerid (VARCHAR, FK)", "shipcountry (VARCHAR)"],
                "sample": "orderid: 10259, customerid: 'CENTC', shipcountry: 'Brazil'"
            }
        },
        "solution":"SELECT orderid, customerid, shipcountry FROM orders WHERE shipcountry IN ('Brazil', 'Mexico', 'Argentina', 'Venezuela')"
    },
    {
        "id":10, 
        "question":"Employees, in order of age", 
        "description": "Sort all employees by their birthdate in ascending order. This query helps identify the age demographics and workforce composition, which is useful for HR planning and diversity analysis.",
        "tables": ["employees"],
        "table_info": {
            "employees": {
                "columns": ["employeeid (INT, PK)", "firstname (VARCHAR)", "lastname (VARCHAR)", "title (VARCHAR)", "birthdate (DATE)"],
                "sample": "employeeid: 9, firstname: 'Anne', lastname: 'Dodsworth', title: 'Sales Representative', birthdate: '1966-01-27'"
            }
        },
        "solution":"SELECT firstname, lastname, title, birthdate FROM employees ORDER BY birthdate"
    },
    {
        "id":11, 
        "question":"Showing only the Date with a DateTime field", 
        "description": "Extract only the date portion from the birthdate field (which may include time). Demonstrates data type casting and formatting for improved readability in reports and user interfaces.",
        "tables": ["employees"],
        "table_info": {
            "employees": {
                "columns": ["employeeid (INT, PK)", "firstname (VARCHAR)", "lastname (VARCHAR)", "birthdate (DATETIME)"],
                "sample": "birthdate: '1966-01-27 00:00:00' ? cast to DATE: '1966-01-27'"
            }
        },
        "solution":"SELECT firstname, lastname, title, CAST(birthdate AS DATE) FROM employees ORDER BY birthdate"
    },
    {
        "id":12, 
        "question":"Employees full name", 
        "description": "Concatenate first and last names to create a full name field. Demonstrates string concatenation for formatted output.",
            "description": "Concatenate the first and last names of employees to create a full name field. This demonstrates string concatenation in SQL, which is useful for creating formatted output for reports and user interfaces.",
        "tables": ["employees"],
        "table_info": {
            "employees": {
                "columns": ["employeeid (INT, PK)", "firstname (VARCHAR)", "lastname (VARCHAR)"],
                "sample": "firstname: 'Nancy', lastname: 'Davolio' ? fullname: 'Nancy Davolio'"
            }
        },
        "solution":"SELECT firstname, lastname, firstname + ' ' + lastname AS fullname FROM employees"
    },
    {
        "id":13, 
        "question":"OrderDetails amount per line item", 
        "description": "Calculate the total price for each order line item by multiplying unit price and quantity. Shows mathematical operations in SQL.",
            "description": "Calculate the total price for each order line item by multiplying the unit price by the quantity. This demonstrates mathematical operations in SQL and is useful for invoice generation and sales analysis.",
        "tables": ["orderdetails"],
        "table_info": {
            "orderdetails": {
                "columns": ["orderid (INT, FK)", "productid (INT, FK)", "unitprice (DECIMAL)", "quantity (INT)", "discount (DECIMAL)"],
                "sample": "orderid: 10248, unitprice: 10.00, quantity: 12 ? totalprice: 120.00"
            }
        },
        "solution":"SELECT orderid, productid, unitprice, quantity, unitprice * quantity AS totalprice FROM orderdetails ORDER BY orderid, productid"
    },
    {
        "id":14, 
        "question":"How many customers?", 
        "description": "Count the total number of unique customers in the database. A basic aggregation query to understand database size.",
            "description": "Count the total number of unique customers in the database. This basic aggregation query helps users understand the size of the customer base, which is important for business growth analysis.",
        "tables": ["customers"],
        "table_info": {
            "customers": {
                "columns": ["customerid (VARCHAR, PK)", "companyname (VARCHAR)", "contactname (VARCHAR)"],
                "sample": "Total customers: 91"
            }
        },
        "solution":"SELECT COUNT(customerid) AS totalcustomers FROM customers"
    },
    {
        "id":15, 
        "question":"When was the first order?", 
        "description": "Find the earliest order date in the system. Uses MIN() aggregate function for temporal analysis.",
            "description": "Find the earliest order date in the system using the MIN() aggregate function. This is useful for understanding how long the business has been operating and for historical sales analysis.",
        "tables": ["orders"],
        "table_info": {
            "orders": {
                "columns": ["orderid (INT, PK)", "orderdate (DATE)"],
                "sample": "First order date: '1996-07-04'"
            }
        },
        "solution":"SELECT MIN(orderdate) AS firstorder FROM orders"
    },
    {
        "id":16, 
        "question":"Countries where there are customers", 
        "description": "Get unique list of all countries with customers. Uses DISTINCT to eliminate duplicates.",
            "description": "Get a unique list of all countries where there are customers. Uses the DISTINCT keyword to eliminate duplicates, which is useful for market expansion and international sales analysis.",
        "tables": ["customers"],
        "table_info": {
            "customers": {
                "columns": ["customerid (VARCHAR, PK)", "country (VARCHAR)"],
                "sample": "Countries: USA, UK, France, Germany, Canada, Brazil, etc."
            }
        },
        "solution":"SELECT DISTINCT country FROM customers"
    },
    {
        "id":17, 
        "question":"Contact titles for customers", 
        "description": "Count customers by contact title and rank them. Shows GROUP BY with aggregation and sorting.",
            "description": "Count the number of customers for each contact title and rank them in descending order. This query uses GROUP BY with aggregation and sorting, which is useful for understanding customer roles and targeting communications.",
        "tables": ["customers"],
        "table_info": {
            "customers": {
                "columns": ["customerid (VARCHAR, PK)", "contacttitle (VARCHAR)"],
                "sample": "contacttitle: 'Sales Manager' (count: 25), 'Owner' (count: 19), etc."
            }
        },
        "solution":"SELECT contacttitle, COUNT(contacttitle) AS total FROM customers GROUP BY contacttitle ORDER BY total DESC"
    },
    {
        "id":18, 
        "question":"Products with associated supplier names", 
        "description": "Link products to their suppliers using INNER JOIN. Shows how to combine data from related tables.",
            "description": "Link each product to its supplier using an INNER JOIN. This query shows how to combine data from related tables and is useful for supply chain management and vendor analysis.",
            "description": "Connect orders with shipping companies to see which carrier was used for each order. Demonstrates JOIN with date formatting. Only orders with orderid less than 10300 are included, which may represent a sample of early orders or a subset for demonstration purposes. This filter should be adjusted or removed for real business analysis.",
        "tables": ["products", "suppliers"],
        "table_info": {
            "products": {"columns": ["productid (INT, PK)", "productname (VARCHAR)", "supplierid (INT, FK)"]},
            "suppliers": {"columns": ["supplierid (INT, PK)", "companyname (VARCHAR)"]},
            "relationship": "products.supplierid ? suppliers.supplierid"
        },
        "solution":"SELECT productid, productname, companyname FROM products INNER JOIN suppliers ON products.supplierid = suppliers.supplierid ORDER BY productid"
    },
    {
        "id":19, 
        "question":"Orders and the Shipper that was used", 
        "description": "Connect orders with shipping companies to see which carrier was used for each order. Demonstrates JOIN with date formatting. Only orders with orderid less than 10300 are included to focus on a specific subset of the data, such as early orders or a sample for demonstration.",
        "tables": ["orders", "shippers"],
        "table_info": {
            "orders": {"columns": ["orderid (INT, PK)", "orderdate (DATE)", "shipvia (INT, FK)"]},
            "shippers": {"columns": ["shipperid (INT, PK)", "companyname (VARCHAR)"]},
            "relationship": "orders.shipvia ? shippers.shipperid"
        },
        "solution":"SELECT orderid, CAST(orderdate AS DATE) AS orderdate, companyname FROM orders INNER JOIN shippers ON orders.shipvia = shippers.shipperid WHERE orderid < 10300 ORDER BY orderid"
    },
    {
        "id":20, 
        "question":"Categories, and the total products in each category", 
        "description": "Count products per category and rank by frequency. Uses JOIN with GROUP BY and aggregation.",
            "description": "Count the number of products in each category and rank categories by the number of products. This query uses JOIN with GROUP BY and aggregation, which is useful for inventory analysis and category management.",
        "tables": ["products", "categories"],
        "table_info": {
            "products": {"columns": ["productid (INT, PK)", "categoryid (INT, FK)"]},
            "categories": {"columns": ["categoryid (INT, PK)", "categoryname (VARCHAR)"]},
            "relationship": "products.categoryid ? categories.categoryid"
        },
        "solution":"SELECT categoryname, COUNT(*) AS totalproducts FROM products INNER JOIN categories ON categories.categoryid = products.categoryid GROUP BY categoryname ORDER BY totalproducts DESC"
    },
    {
        "id":21, 
        "question":"Total customers per country/city", 
        "description": "Analyze customer distribution by geography. Uses GROUP BY with multiple columns and sorting.",
            "description": "Analyze the distribution of customers by city and country. Uses GROUP BY with multiple columns and sorting, which is useful for geographic market analysis and sales planning.",
        "tables": ["customers"],
        "table_info": {
            "customers": {
                "columns": ["customerid (VARCHAR, PK)", "city (VARCHAR)", "country (VARCHAR)"],
                "sample": "city: 'London', country: 'UK' (count: 4), city: 'Berlin', country: 'Germany' (count: 2)"
            }
        },
        "solution":"SELECT city, country, COUNT(*) AS total FROM customers GROUP BY country, city ORDER BY total DESC"
    },
    {
        "id":22, 
        "question":"Products that need reordering", 
        "description": "Identify low stock products where units in stock fall below reorder level. Critical for inventory management.",
            "description": "Identify products where the number of units in stock is less than the reorder level. This is critical for inventory management, as it helps prevent stockouts and ensures timely reordering.",
        "tables": ["products"],
        "table_info": {
            "products": {
                "columns": ["productid (INT, PK)", "productname (VARCHAR)", "unitsinstock (INT)", "reorderlevel (INT)"],
                "sample": "productid: 12, unitsinstock: 0, reorderlevel: 30 (needs reordering)"
            }
        },
        "solution":"SELECT productid, productname, unitsinstock, reorderlevel FROM products WHERE unitsinstock < reorderlevel ORDER BY productid"
    },
    {
        "id":23, 
        "question":"Products that need reordering, continued", 
        "description": "Advanced inventory check considering both stock and on-order quantities. Only shows active products (not discontinued).",
            "description": "Advanced inventory check: identify products where the sum of units in stock and units on order is less than or equal to the reorder level, and the product is not discontinued. This helps ensure only active products are considered for reordering.",
        "tables": ["products"],
        "table_info": {
            "products": {
                "columns": ["productid (INT, PK)", "productname (VARCHAR)", "unitsinstock (INT)", "unitsonorder (INT)", "reorderlevel (INT)", "discontinued (BIT)"],
                "sample": "When (unitsinstock + unitsonorder) <= reorderlevel AND discontinued = 0"
            }
        },
        "solution":"SELECT productid, productname, unitsinstock, unitsonorder, reorderlevel, discontinued FROM products WHERE unitsinstock + unitsonorder <= reorderlevel AND discontinued = 0 ORDER BY productid"
    },
    {
        "id":24, 
        "question":"Customer list by region", 
        "description": "Sort customers with region handling. Uses CASE statement to prioritize customers with null regions.",
            "description": "Sort customers by region, placing those with a region value first and those with NULL regions last. Uses a CASE statement to prioritize, which is useful for regional sales management and reporting.",
        "tables": ["customers"],
        "table_info": {
            "customers": {
                "columns": ["customerid (VARCHAR, PK)", "companyname (VARCHAR)", "region (VARCHAR)"],
                "sample": "Customers with regions first, then those without (NULL values last)"
            }
        },
        "solution":"SELECT customerid, companyname, region FROM customers ORDER BY (CASE WHEN region IS NULL THEN 1 ELSE 0 END), region, customerid"
    },
    {
        "id":25, 
        "question":"High freight charges", 
        "description": "Find top 3 countries with highest average shipping costs. Shows use of TOP clause and GROUP BY.",
            "description": "Find the top 3 countries with the highest average shipping (freight) costs. Uses the TOP clause and GROUP BY, which is useful for identifying expensive shipping destinations and optimizing logistics.",
        "tables": ["orders"],
        "table_info": {
            "orders": {
                "columns": ["orderid (INT, PK)", "shipcountry (VARCHAR)", "freight (DECIMAL)"],
                "sample": "shipcountry: 'Sweden', averagefreight: 205.38"
            }
        },
        "solution":"SELECT TOP 3 shipcountry, AVG(freight) AS averagefreight FROM orders GROUP BY shipcountry ORDER BY averagefreight DESC"
    },
    {
        "id":26, 
        "question":"High freight charges - 2015", 
        "description": "Analyze shipping costs filtered by year. Demonstrates date filtering for temporal analysis.",
            "description": "Analyze shipping (freight) costs for orders placed in the year 2015. Demonstrates date filtering for temporal analysis, which is useful for year-over-year cost comparisons.",
        "tables": ["orders"],
        "table_info": {
            "orders": {
                "columns": ["orderid (INT, PK)", "shipcountry (VARCHAR)", "freight (DECIMAL)", "orderdate (DATE)"],
                "sample": "Data filtered for orders between 2015-01-01 and 2016-01-01"
            }
        },
        "solution":"SELECT TOP 3 shipcountry, AVG(freight) AS averagefreight FROM orders WHERE orderdate >= '20150101' AND orderdate < '20160101' GROUP BY shipcountry ORDER BY averagefreight DESC"
    },
    {
        "id":27, 
        "question":"High freight charges with between", 
        "description": "Alternative approach using different date format. Shows flexibility in SQL date comparisons.",
            "description": "Alternative approach to analyzing shipping costs for a specific year, using a different date format or method. Shows flexibility in SQL date comparisons for temporal analysis.",
        "tables": ["orders"],
        "table_info": {
            "orders": {
                "columns": ["orderid (INT, PK)", "shipcountry (VARCHAR)", "freight (DECIMAL)", "orderdate (DATE)"],
                "sample": "Top 3 countries by average freight in a specific year"
            }
        },
        "solution":"SELECT TOP 3 shipcountry, AVG(freight) AS averagefreight FROM orders WHERE orderdate >= '20150101' AND orderdate < '20160101' GROUP BY shipcountry ORDER BY averagefreight DESC"
    },
    {
        "id":28, 
        "question":"High freight charges - last year", 
        "description": "Dynamic date filtering using DATEADD function. Calculates based on most recent order date.",
            "description": "Analyze shipping costs for the last year relative to the most recent order date in the system. Uses the DATEADD function for dynamic date filtering, which is useful for rolling year analysis.",
        "tables": ["orders"],
        "table_info": {
            "orders": {
                "columns": ["orderid (INT, PK)", "shipcountry (VARCHAR)", "freight (DECIMAL)", "orderdate (DATE)"],
                "sample": "Data from the last year relative to the latest order in the system"
            }
        },
        "solution":"SELECT TOP 3 shipcountry, AVG(freight) AS averagefreight FROM orders WHERE orderdate >= DATEADD(year, -1, (SELECT MAX(orderdate) FROM orders)) GROUP BY shipcountry ORDER BY averagefreight DESC"
    },
    {
        "id":29, 
        "question":"Inventory list", 
        "description": "Create comprehensive inventory snapshot with employee and product information. Complex multi-table JOIN.",
            "description": "Create a comprehensive inventory snapshot by joining orders, employees, order details, and products. This complex multi-table JOIN provides detailed information for inventory tracking and employee performance analysis.",
        "tables": ["orders", "employees", "orderdetails", "products"],
        "table_info": {
            "orders": {"columns": ["orderid (INT, PK)", "employeeid (INT, FK)"]},
            "employees": {"columns": ["employeeid (INT, PK)", "lastname (VARCHAR)"]},
            "orderdetails": {"columns": ["orderid (INT, FK)", "productid (INT, FK)", "quantity (INT)"]},
            "products": {"columns": ["productid (INT, PK)", "productname (VARCHAR)"]},
            "relationship": "Multiple JOINs connecting all tables"
        },
        "solution":"SELECT orders.employeeid, employees.lastname, orders.orderid, products.productname, orderdetails.quantity FROM orders INNER JOIN employees ON orders.employeeid = employees.employeeid INNER JOIN orderdetails ON orders.orderid = orderdetails.orderid INNER JOIN products ON products.productid = orderdetails.productid ORDER BY orderid, products.productid"
    },
    {
        "id":30, 
        "question":"Customers with no orders", 
        "description": "Find inactive customers who have never placed orders. Uses LEFT JOIN to identify missing matches.",
            "description": "Find customers who have never placed an order by using a LEFT JOIN to identify missing matches. This is useful for identifying inactive customers and targeting them for marketing or outreach.",
        "tables": ["customers", "orders"],
        "table_info": {
            "customers": {"columns": ["customerid (VARCHAR, PK)", "companyname (VARCHAR)"]},
            "orders": {"columns": ["orderid (INT, PK)", "customerid (VARCHAR, FK)"]},
            "relationship": "customers.customerid ? orders.customerid (LEFT JOIN)"
        },
        "solution":"SELECT customers.customerid, orders.customerid FROM customers LEFT JOIN orders ON orders.customerid = customers.customerid WHERE orders.customerid IS NULL"
    },
    {
        "id":31, 
        "question":"Customers with no orders for EmployeeID 4", 
        "description": "Find customers who haven't bought from a specific salesman. Shows conditional LEFT JOIN logic.",
            "description": "Find customers who have not placed any orders with the employee whose EmployeeID is 4. Uses conditional LEFT JOIN logic, which is useful for analyzing sales coverage and identifying new business opportunities.",
        "tables": ["customers", "orders"],
        "table_info": {
            "customers": {"columns": ["customerid (VARCHAR, PK)", "companyname (VARCHAR)"]},
            "orders": {"columns": ["orderid (INT, PK)", "customerid (VARCHAR, FK)", "employeeid (INT)"]},
            "relationship": "customers.customerid ? orders.customerid WHERE employeeid = 4"
        },
        "solution":"SELECT customers.customerid, orders.customerid FROM customers LEFT JOIN orders ON orders.customerid = customers.customerid AND orders.employeeid = '4' WHERE orders.customerid IS NULL"
    },
    {
        "id":32, 
        "question":"High-value customers", 
        "description": "Identify individual high-value orders in 2016. Uses aggregation with HAVING clause and multiple table joins.",
            "description": "Identify individual orders in 2016 where the total order amount exceeds 10,000. Uses aggregation with HAVING clause and multiple table joins, which is useful for high-value sales analysis and customer segmentation.",
        "tables": ["customers", "orders", "orderdetails"],
        "table_info": {
            "customers": {"columns": ["customerid (VARCHAR, PK)", "companyname (VARCHAR)"]},
            "orders": {"columns": ["orderid (INT, PK)", "customerid (VARCHAR, FK)", "orderdate (DATE)"]},
            "orderdetails": {"columns": ["orderid (INT, FK)", "quantity (INT)", "unitprice (DECIMAL)"]},
            "relationship": "Multiple JOINs with aggregation"
        },
        "solution":"SELECT c.customerid, c.companyname, o.orderid, SUM(od.quantity * od.unitprice) AS totalorderamount FROM customers AS c INNER JOIN orders AS o ON o.customerid = c.customerid INNER JOIN orderdetails AS od ON od.orderid = o.orderid WHERE YEAR(o.orderdate) = 2016 GROUP BY c.customerid, c.companyname, o.orderid HAVING SUM(od.quantity * od.unitprice) > '10000' ORDER BY totalorderamount DESC"
    },
    {
        "id":33, 
        "question":"High-value customers - total orders", 
        "description": "Aggregate high-value customers' total spending in 2016. Shows how to sum across multiple orders.",
            "description": "Aggregate the total spending of high-value customers in 2016 by summing across all their orders. Shows how to use GROUP BY and HAVING to identify top customers for loyalty programs or targeted marketing.",
        "tables": ["customers", "orders", "orderdetails"],
        "table_info": {
            "customers": {"columns": ["customerid (VARCHAR, PK)", "companyname (VARCHAR)"]},
            "orders": {"columns": ["orderid (INT, PK)", "customerid (VARCHAR, FK)", "orderdate (DATE)"]},
            "orderdetails": {"columns": ["orderid (INT, FK)", "quantity (INT)", "unitprice (DECIMAL)"]},
            "relationship": "Group all orders per customer and sum totals"
        },
        "solution":"SELECT c.customerid, c.companyname, SUM(od.quantity * od.unitprice) AS totalorderamount FROM customers AS c INNER JOIN orders AS o ON o.customerid = c.customerid INNER JOIN orderdetails AS od ON od.orderid = o.orderid WHERE YEAR(o.orderdate) = 2016 GROUP BY c.customerid, c.companyname HAVING SUM(od.quantity * od.unitprice) >= '15000' ORDER BY totalorderamount DESC"
    },
    {
        "id":34, 
        "question":"High-value customers - with discount", 
        "description": "Calculate actual revenue after applying discounts. Shows business logic with discount calculations.",
            "description": "Calculate the actual revenue from each customer in 2016 after applying discounts. Shows business logic with discount calculations, which is important for accurate revenue reporting and profitability analysis.",
        "tables": ["customers", "orders", "orderdetails"],
        "table_info": {
            "customers": {"columns": ["customerid (VARCHAR, PK)", "companyname (VARCHAR)"]},
            "orders": {"columns": ["orderid (INT, PK)", "customerid (VARCHAR, FK)", "orderdate (DATE)"]},
            "orderdetails": {"columns": ["orderid (INT, FK)", "quantity (INT)", "unitprice (DECIMAL)", "discount (DECIMAL)"]},
            "relationship": "Calculate: total = SUM(quantity * unitprice * (1 - discount))"
        },
        "solution":"SELECT c.customerid, c.companyname, SUM(od.quantity * od.unitprice) AS totalswithoutdiscount, SUM(od.quantity * od.unitprice * (1 - discount)) AS totalswithdiscount FROM customers AS c JOIN orders AS o ON o.customerid = c.customerid JOIN orderdetails AS od ON o.orderid = od.orderid WHERE orderdate >= '20160101' AND orderdate < '20170101' GROUP BY c.customerid, c.companyname HAVING SUM(od.quantity * od.unitprice * (1 - discount)) > 10000 ORDER BY totalswithdiscount DESC"
    },
    {"id": 201, "type": "mcq", "question": "What will COUNT(column_name) return if the column contains NULL values?", "options": ["A) Total rows including NULLs", "B) Total rows excluding NULLs", "C) Only NULL rows", "D) Error"], "correct_answers": ["B"], "complexity": "easy", "topic": "SQL"},
    {"id": 202, "type": "mcq", "question": "What is the result of the following query? SELECT COUNT(*) FROM employees WHERE salary > 5000;", "options": ["A) Number of non-NULL salaries", "B) Number of rows where salary is not NULL", "C) Number of rows where salary > 5000", "D) Total number of rows"], "correct_answers": ["C"], "complexity": "easy", "topic": "SQL"},
    {"id": 203, "type": "mcq", "question": "Which clause is evaluated first in a SQL SELECT statement?", "options": ["A) SELECT", "B) ORDER BY", "C) FROM", "D) WHERE"], "correct_answers": ["C"], "complexity": "easy", "topic": "SQL"},
    {"id": 204, "type": "mcq", "question": "What is the difference between WHERE and HAVING?", "options": ["A) WHERE works on groups, HAVING works on rows", "B) Both are identical", "C) WHERE filters rows, HAVING filters groups", "D) HAVING executes before WHERE"], "correct_answers": ["C"], "complexity": "easy", "topic": "SQL"},
    {"id": 205, "type": "mcq", "question": "Which query correctly returns departments with more than 5 employees?", "options": ["A) SELECT dept_id FROM emp WHERE COUNT(*) > 5;", "B) SELECT dept_id FROM emp GROUP BY dept_id WHERE COUNT(*) > 5;", "C) SELECT dept_id FROM emp GROUP BY dept_id HAVING COUNT(*) > 5;", "D) SELECT dept_id FROM emp HAVING COUNT(*) > 5;"], "correct_answers": ["C"], "complexity": "easy", "topic": "SQL"},
    {"id": 206, "type": "mcq", "question": "What does the following query return? SELECT DISTINCT dept_id FROM employees;", "options": ["A) All rows", "B) One row per employee", "C) Unique department IDs", "D) Department count"], "correct_answers": ["C"], "complexity": "easy", "topic": "SQL"},
    {"id": 207, "type": "mcq", "question": "Which JOIN returns rows even when there is no match in the right table?", "options": ["A) INNER JOIN", "B) FULL JOIN", "C) LEFT JOIN", "D) CROSS JOIN"], "correct_answers": ["C"], "complexity": "easy", "topic": "SQL"},
    {"id": 208, "type": "mcq", "question": "What happens if a subquery returns more than one row but is used with = ?", "options": ["A) First row is used", "B) All rows are compared", "C) Query fails with an error", "D) NULL is returned"], "correct_answers": ["C"], "complexity": "easy", "topic": "SQL"},
    {"id": 209, "type": "mcq", "question": "Which operator should be used when a subquery returns multiple rows?", "options": ["A) =", "B) EXISTS", "C) IN", "D) LIKE"], "correct_answers": ["C"], "complexity": "easy", "topic": "SQL"},
    {"id": 210, "type": "mcq", "question": "What does EXISTS return?", "options": ["A) Number of rows", "B) Actual data", "C) TRUE or FALSE", "D) NULL"], "correct_answers": ["C"], "complexity": "easy", "topic": "SQL"},
    {"id": 211, "type": "mcq", "question": "What is the result of this query? SELECT 1 + NULL;", "options": ["A) 1", "B) 0", "C) NULL", "D) Error"], "correct_answers": ["C"], "complexity": "easy", "topic": "SQL"},
    {"id": 212, "type": "mcq", "question": "Which SQL operation is NOT reversible using ROLLBACK?", "options": ["A) INSERT", "B) UPDATE", "C) DELETE", "D) DROP TABLE"], "correct_answers": ["D"], "complexity": "medium", "topic": "SQL"},
    {"id": 213, "type": "mcq", "question": "What does TRUNCATE do compared to DELETE?", "options": ["A) Deletes rows one by one", "B) Can be rolled back", "C) Fires triggers", "D) Removes all rows efficiently and cannot be rolled back"], "correct_answers": ["D"], "complexity": "medium", "topic": "SQL"},
    {"id": 214, "type": "mcq", "question": "Which query returns the second highest salary?", "options": ["A) SELECT MAX(salary) FROM emp;", "B) SELECT salary FROM emp ORDER BY salary LIMIT 1;", "C) SELECT MAX(salary) FROM emp WHERE salary < (SELECT MAX(salary) FROM emp);", "D) SELECT salary FROM emp WHERE salary = 2;"], "correct_answers": ["C"], "complexity": "medium", "topic": "SQL"},
    {"id": 215, "type": "mcq", "question": "What does UNION do by default?", "options": ["A) Combines result sets including duplicates", "B) Sorts data", "C) Combines result sets and removes duplicates", "D) Joins tables"], "correct_answers": ["C"], "complexity": "easy", "topic": "SQL"},
    {"id": 216, "type": "mcq", "question": "Which SQL keyword is used to return rows where a column value is missing?", "options": ["A) = NULL", "B) NOT NULL", "C) IS NULL", "D) EMPTY"], "correct_answers": ["C"], "complexity": "easy", "topic": "SQL"},
    {"id": 217, "type": "mcq", "question": "What happens if GROUP BY is used without aggregate functions?", "options": ["A) Error", "B) Returns random rows", "C) Returns distinct combinations of grouped columns", "D) Returns NULL"], "correct_answers": ["C"], "complexity": "easy", "topic": "SQL"},
    {"id": 218, "type": "mcq", "question": "Which constraint allows only values that meet a specific condition?", "options": ["A) UNIQUE", "B) FOREIGN KEY", "C) CHECK", "D) DEFAULT"], "correct_answers": ["C"], "complexity": "easy", "topic": "SQL"},
    {"id": 219, "type": "mcq", "question": "What does a CROSS JOIN produce?", "options": ["A) Matched rows only", "B) Left table rows only", "C) Cartesian product of both tables", "D) Grouped rows"], "correct_answers": ["C"], "complexity": "easy", "topic": "SQL"},
    {"id": 220, "type": "mcq", "question": "Which SQL feature guarantees all statements succeed or none are applied?", "options": ["A) Index", "B) Trigger", "C) View", "D) Transaction"], "correct_answers": ["D"], "complexity": "easy", "topic": "SQL"},
]



# ==========================
# Power BI Question Bank with MCQ
# ==========================
POWERBI_QUESTIONS = [
    {"id": 101, "type": "mcq", "question": "A dataset that includes _ can be used to create a map visualization. (Select all that apply.)", "options": ["A. house numbers, street names", "B. geospatial data", "C. city names, country names", "D. longitude, latitude"], "correct_answers": ["B", "C", "D"], "complexity": "easy", "topic": "Visualizations"},
    {"id": 102, "type": "mcq", "question": "How do you create a chart visual in Power BI Desktop Report view? (Select all that apply.)", "options": ["A. Click New Visual on the Home tab.", "B. Select a chart visual in the Visualizations pane.", "C. Click New Visual on the Data Tools tab.", "D. Select a field that contains values."], "correct_answers": ["A", "B", "D"], "complexity": "easy", "topic": "Report Creation"},
    {"id": 103, "type": "mcq", "question": "What daily sales number does this DAX measure formula calculate? CALCULATE(SUM([Sales]),DATESMTD([Date]))", "options": ["A. running total sales in each month that starts over each month", "B. total sales for the entire month", "C. running total in entire year for the entire month", "D. rolling average over 12 months of sales"], "correct_answers": ["A"], "complexity": "medium", "topic": "DAX Functions"},
    {"id": 104, "type": "mcq", "question": "You are creating a report in Power BI Desktop and want to restrict the data to records where Country='Canada'. To accomplish this, what do you need to create?", "options": ["A. a directive", "B. a custom column", "C. an indexed column", "D. a parameter"], "correct_answers": ["B"], "complexity": "medium", "topic": "Data Filtering"},
    {"id": 105, "type": "mcq", "question": "What is the primary benefit of using visualizations such as line charts, bar charts, and column charts?", "options": ["A. They are easier to create than other visualizations.", "B. They require fewer resources than more complex visualizations.", "C. They are also used in Excel, so they feel familiar to users.", "D. They are free to use."], "correct_answers": ["C"], "complexity": "easy", "topic": "Visualizations"},
    {"id": 106, "type": "mcq", "question": "In Power BI service, deleted pages are available after deletion until", "options": ["A. midnight of the day on which they are deleted", "B. the next billing cycle", "C. you empty the Recycle Bin", "D. the report has been saved"], "correct_answers": ["C"], "complexity": "medium", "topic": "Power BI Service"},
    {"id": 107, "type": "mcq", "question": "You need to add a required color to a bar chart. How can you add an exact color value to an existing bar chart?", "options": ["A. Click the color in the visual (e.g., the bars) and right-click to select the color.", "B. You cannot select custom colors in a bar chart or related visual.", "C. Select the value closest to this color from the color formatting options.", "D. Enter the hex value into the color formatting options."], "correct_answers": ["D"], "complexity": "medium", "topic": "Formatting"},
    {"id": 108, "type": "mcq", "question": "The Excel function IF is nearly the same as which DAX function?", "options": ["A. SWITCH", "B. IF", "C. IFX", "D. IFS"], "correct_answers": ["B"], "complexity": "easy", "topic": "DAX Functions"},
    {"id": 109, "type": "mcq", "question": "Power BI's Publish to Web option allows you to embed visualizations within _. (Select all that apply.)", "options": ["A. blog posts", "B. email messages", "C. web sites", "D. text messages"], "correct_answers": ["A", "C"], "complexity": "medium", "topic": "Power BI Service"},
    {"id": 110, "type": "mcq", "question": "What can you do within the Power BI Desktop Query Settings pane? (Select all that apply.)", "options": ["A. Rename a query step.", "B. Delete a query step.", "C. Delete from one query step to the end.", "D. Reorder the steps."], "correct_answers": ["A", "B", "C", "D"], "complexity": "medium", "topic": "Power Query"},
    {"id": 111, "type": "mcq", "question": "After you enter text in the Q&A box or Q&A visual, Power BI will _ your data to create a list of appropriate visualizations.", "options": ["A. filter and group", "B. sort and filter", "C. sort, filter, and group", "D. sort and group"], "correct_answers": ["B"], "complexity": "easy", "topic": "Q&A Feature"},
    {"id": 112, "type": "mcq", "question": "You just deleted a dashboard in the Power BI service and want to get it back. What should you do?", "options": ["A. Press Ctrl+Z.", "B. Select Undo from the toolbar.", "C. You cannot undo the deletion of a dashboard.", "D. Recover it from the Recycle Bin."], "correct_answers": ["D"], "complexity": "easy", "topic": "Power BI Service"},
    {"id": 113, "type": "mcq", "question": "You have a sales data source and want to relate the tables. The table that contains sales transactions is a _ table that contains product information is a _ table.", "options": ["A. dimension; fact", "B. lookup; data", "C. fact; dimension", "D. data; supporting"], "correct_answers": ["C"], "complexity": "medium", "topic": "Data Modeling"},
    {"id": 114, "type": "mcq", "question": "When you are creating a formula in the Power Query Editor, what does IntelliSense provide a list of? (Select all that apply.)", "options": ["A. columns", "B. tables", "C. functions", "D. data sources"], "correct_answers": ["A", "C"], "complexity": "easy", "topic": "Power Query"},
    {"id": 115, "type": "mcq", "question": "You want to delete a dataset but the Power BI service will not let you. What is the most likely cause?", "options": ["A. A tile on your dashboard contains data from that dataset.", "B. The dataset is already being used in a published app.", "C. A report contains data from that dataset.", "D. The dataset is in your workspace."], "correct_answers": ["C"], "complexity": "medium", "topic": "Power BI Service"},
    {"id": 116, "type": "mcq", "question": "One of your data columns includes the city, state, and postal code line of a mailing address. You need to separate the fields so you can access the geospatial elements for a map visualization. What transformation should you apply?", "options": ["A. Replace values", "B. Split column", "C. Modify data type", "D. Best fit geospatial"], "correct_answers": ["B"], "complexity": "medium", "topic": "Data Transformation"},
    {"id": 117, "type": "mcq", "question": "What tool can you use in Power BI Desktop to reduce data?", "options": ["A. report editor", "B. Power Query Editor", "C. dashboard", "D. data modeler"], "correct_answers": ["B"], "complexity": "easy", "topic": "Power Query"},
    {"id": 118, "type": "mcq", "question": "What is NOT a valid data connection type for Power BI Desktop?", "options": ["A. Azure data", "B. file data", "C. relationships data", "D. database data"], "correct_answers": ["C"], "complexity": "medium", "topic": "Data Connections"},
    {"id": 119, "type": "mcq", "question": "Which data type can be uploaded directly to powerbi.com?", "options": ["A. Excel files", "B. comma-separated value (CSV) files", "C. Power BI Desktop files", "D. all of these answers"], "correct_answers": ["D"], "complexity": "easy", "topic": "Power BI Service"},
    {"id": 120, "type": "mcq", "question": "What does Power BI Premium provide?", "options": ["A. Power BI Report Server", "B. report sharing without a per-user license", "C. all of these answers", "D. dedicated capacity for your company"], "correct_answers": ["C"], "complexity": "medium", "topic": "Power BI Premium"},
    {"id": 121, "type": "mcq", "question": "You have a report in Power BI service and want to save the state of a report page for easy access. What feature helps you do this?", "options": ["A. views", "B. filters", "C. bookmarks", "D. slicers"], "correct_answers": ["C"], "complexity": "easy", "topic": "Report Features"},
    {"id": 122, "type": "mcq", "question": "What should you do to increase the readability of a report?", "options": ["A. all of these answers", "B. Remove unnecessary field labels.", "C. Select the most appropriate visualization.", "D. Use borders."], "correct_answers": ["A"], "complexity": "easy", "topic": "Report Design"},
    {"id": 123, "type": "mcq", "question": "Which feature in the Power BI service is most useful when you need to create pages that present the same visualizations for different territories, salespeople, or teams?", "options": ["A. landscape mode", "B. none of these answers", "C. Shrink to Fit", "D. templates"], "correct_answers": ["D"], "complexity": "medium", "topic": "Report Features"},
    {"id": 124, "type": "mcq", "question": "What should you use to highlight a specific visualization in a report?", "options": ["A. Spotlight", "B. Highlight", "C. Magnify", "D. None of the answers"], "correct_answers": ["A"], "complexity": "easy", "topic": "Report Features"},
    {"id": 125, "type": "mcq", "question": "What does My Workspace on powerbi.com include?", "options": ["A. Visualizations and a fields list", "B. Toolbars and preferences", "C. Workbooks and visualizations", "D. Dashboards and reports"], "correct_answers": ["D"], "complexity": "easy", "topic": "Power BI Service"},
    {"id": 126, "type": "mcq", "question": "You want to access the underlying data for a specific data point in a visualization. What should you choose?", "options": ["A. Drill up", "B. Drill down", "C. Expand to next level", "D. Collapse"], "correct_answers": ["B"], "complexity": "easy", "topic": "Drill Functions"},
    {"id": 127, "type": "mcq", "question": "You have a treemap visualization that groups by sales territory. To allow users to further analyze data for a specific territory, what filter should you apply?", "options": ["A. Visual level", "B. Page level", "C. Drillthrough", "D. Expand down"], "correct_answers": ["C"], "complexity": "medium", "topic": "Filtering"},
    {"id": 128, "type": "mcq", "question": "Facebook, Twilio, GitHub, and MailChimp are all examples of Power BI _.", "options": ["A. online services", "B. Wiki data sources", "C. database data sources", "D. File data sources"], "correct_answers": ["A"], "complexity": "easy", "topic": "Data Connections"},
    {"id": 129, "type": "mcq", "question": "When you use Publish to Web in the Power BI service, who can view your published content?", "options": ["A. everyone in your environment", "B. anyone on the internet", "C. everyone in your organization", "D. only you"], "correct_answers": ["B"], "complexity": "medium", "topic": "Power BI Service"},
    {"id": 130, "type": "mcq", "question": "The iterator functions SUMX and AVERAGEX are used to perform calculations _.", "options": ["A. for Power BI mobile apps", "B. in Power BI service rather than Power BI desktop", "C. in the context of a record", "D. for very large datasets"], "correct_answers": ["C"], "complexity": "medium", "topic": "DAX Functions"},
    {"id": 131, "type": "mcq", "question": "In Power BI Desktop Model view, what type of join will yield all results from Table 1 and any matching results from Table 2?", "options": ["A. Right Outer Join", "B. Left Outer Join", "C. Left Inner Join", "D. Right Inner Join"], "correct_answers": ["B"], "complexity": "medium", "topic": "Data Modeling"},
    {"id": 132, "type": "mcq", "question": "What is NOT a built-in Power BI visual?", "options": ["A. Power KPI", "B. funnel chart", "C. waterfall chart", "D. ArcGIS map"], "correct_answers": ["A"], "complexity": "hard", "topic": "Visualizations"},
    {"id": 133, "type": "mcq", "question": "You want to combine several CSV files into a single data file after you connect a folder. What must be true about these CSV data files? (Select all that apply.)", "options": ["A. They must be stored in the same folder.", "B. They must have the same schema.", "C. They must have the same file type.", "D. They must have no duplicate data rows."], "correct_answers": ["A", "B", "C"], "complexity": "medium", "topic": "Data Loading"},
    {"id": 134, "type": "mcq", "question": "If you delete a dataset in the Power BI service, what happens to the dashboards and reports supported by the dataset?", "options": ["A. They will be stored as static dashboards and reports.", "B. They will be deleted.", "C. They will be converted to image files.", "D. Nothing—they will be unchanged."], "correct_answers": ["B"], "complexity": "medium", "topic": "Power BI Service"},
    {"id": 135, "type": "mcq", "question": "Which DAX function compares a column of values in Table A with a similar column in Table B, and returns the values that are not found in Table B?", "options": ["A. COMPARE", "B. FINDUNIQUE", "C. EXCEPT", "D. SWITCH"], "correct_answers": ["C"], "complexity": "hard", "topic": "DAX Functions"},
    {"id": 136, "type": "mcq", "question": "Your data model includes two related tables, Customers and Orders. To determine the number of customers that have placed orders, create a measure on the _ table using the _ function.", "options": ["A. Orders; DISTINCTCOUNT", "B. Customers; COUNT", "C. Orders; COUNT", "D. Customers; DISTINCTCOUNT"], "correct_answers": ["D"], "complexity": "hard", "topic": "DAX Functions"},
    {"id": 137, "type": "mcq", "question": "Power BI works best with tables that are _.", "options": ["A. short and wide", "B. long and skinny", "C. short and skinny", "D. long and wide"], "correct_answers": ["B"], "complexity": "medium", "topic": "Data Modeling"},
    {"id": 138, "type": "mcq", "question": "You have two columns of numerical data and want to create a visual to help determine if there is a relationship between them. What kind of chart is designed to do this?", "options": ["A. bar chart", "B. bubble chart", "C. line chart", "D. scatter chart"], "correct_answers": ["D"], "complexity": "easy", "topic": "Visualizations"},
    {"id": 139, "type": "mcq", "question": "In the report editor, which task can you NOT accomplish using drag and drop?", "options": ["A. Add more information to a visualization.", "B. All of these tasks can be done with drag and drop.", "C. Create a new visualization.", "D. Rearrange and resize visualizations."], "correct_answers": ["B"], "complexity": "medium", "topic": "Report Creation"},
    {"id": 140, "type": "mcq", "question": "In general, what is the best way to shape your data for Power BI?", "options": ["A. User a star schema.", "B. Load all tables from the data source.", "C. all of these answers", "D. Include multiple objects in each data table."], "correct_answers": ["A"], "complexity": "hard", "topic": "Data Modeling"},
    {"id": 141, "type": "mcq", "question": "You can optionally include a filter in which DAX function?", "options": ["A. CALCULATE", "B. SUM", "C. PICARD", "D. COMPARE"], "correct_answers": ["A"], "complexity": "hard", "topic": "DAX Functions"},
    {"id": 142, "type": "mcq", "question": "Which feature is not in the Power BI Admin portal?", "options": ["A. usage metrics", "B. organization visuals", "C. Dashboard Manager", "D. audit logs"], "correct_answers": ["C"], "complexity": "medium", "topic": "Power BI Service"},
    {"id": 143, "type": "mcq", "question": "You want to count the number of products in the Products data table. Which DAX function works best?", "options": ["A. RECOUNT", "B. COUNTUNIQUE", "C. COUNTX", "D. COUNTROWS"], "correct_answers": ["D"], "complexity": "medium", "topic": "DAX Functions"},
    {"id": 144, "type": "mcq", "question": "You have just pinned a visualization to a new dashboard. Before you can add another visualization, what must you do?", "options": ["A. Save it.", "B. Name it.", "C. Refresh it.", "D. Publish it."], "correct_answers": ["B"], "complexity": "easy", "topic": "Dashboard Creation"},
    {"id": 145, "type": "mcq", "question": "You can create a live connection to _.", "options": ["A. Dynamics 365", "B. SharePoint", "C. all of these answers", "D. SQL Server Analysis Services"], "correct_answers": ["C"], "complexity": "hard", "topic": "Data Connections"},
    {"id": 146, "type": "mcq", "question": "What is the purpose of this code? ProductCount = COUNT(Products[ProductID])", "options": ["A. It is part of the documentation", "B. It creates and formats a measure called ProductCount", "C. It creates a measure called ProductCount", "D. It calculates the value for an existing measure named ProductCount"], "correct_answers": ["C"], "complexity": "medium", "topic": "DAX Functions"},
    {"id": 147, "type": "mcq", "question": "Your computer rental dataset includes columns for StartTime, EndTime, and PerHourRate. What two DAX functions could you use to calculate the total earned for rentals?", "options": ["A. DATEDIFF and SUM", "B. DATEDIFF and SUMX", "C. TIMEDIFF and SUM", "D. TIMEDIFF and SUMX"], "correct_answers": ["B"], "complexity": "hard", "topic": "DAX Functions"},
]

# ==========================
# Question Complexity Assignment & Shuffling
# ==========================

def assign_complexity_level(question):
    """
    Assign complexity levels based on SQL features:
    1 (Beginner): Simple SELECT, WHERE with basic operators
    2 (Intermediate): JOINs, GROUP BY, HAVING, subqueries, LIKE
    3 (Advanced): Complex joins, multiple aggregations, complex WHERE, CASE statements
    """
    solution = question.get("solution", "").lower()
    num_tables = len(question.get("tables", []))
    
    # Count SQL keywords
    joins = solution.count("join")
    group_by = solution.count("group by")
    having = solution.count("having")
    case_when = solution.count("case")
    subquery = solution.count("select") > 1
    distinct = solution.count("distinct")
    
    complexity_score = 0
    
    # Basic scoring
    if joins > 0:
        complexity_score += joins * 2
    if group_by > 0:
        complexity_score += 1
    if having > 0:
        complexity_score += 1
    if case_when > 0:
        complexity_score += 2
    if subquery:
        complexity_score += 2
    if distinct:
        complexity_score += 0.5
    
    # Table count factor
    if num_tables > 2:
        complexity_score += 1
    
    # Determine level
    if complexity_score >= 4:
        return 3  # Advanced
    elif complexity_score >= 1.5:
        return 2  # Intermediate
    else:
        return 1  # Beginner

# Add complexity level to each question
for question in QUESTIONS:
    question["complexity"] = assign_complexity_level(question)

# Assign complexity to PowerBI questions (they already have complexity field)
for question in POWERBI_QUESTIONS:
    if "complexity" not in question:
        complexity_map = {"easy": 1, "medium": 2, "hard": 3}
        question["complexity"] = complexity_map.get(question.get("complexity", "medium"), 2)

def get_shuffled_questions(user_name):
    """
    Create a deterministic shuffled order of questions for a user.
    - Returns 20 SQL questions (beginner + intermediate only) + 20 PowerBI questions (prefer easy, fill with medium if needed)
    - Uses user's name as seed for consistent randomization
    """
    # Create a hash seed from the user's name
    seed = int(hashlib.md5(user_name.lower().encode()).hexdigest(), 16)
    random.seed(seed)
    
    # Select 20 SQL questions as TWO groups: 10 MCQ (topic='SQL' & type='mcq') + 10 practice SQL (type='sql')
    # Keep same complexity restrictions (beginner + intermediate) and JOIN-safety for practice items.
    def _complexity_value_local(q):
        c = q.get('complexity', 1)
        if isinstance(c, int):
            return c
        if isinstance(c, str):
            return {'easy': 1, 'medium': 2, 'hard': 3}.get(c.lower(), 2)
        try:
            return int(c)
        except Exception:
            return 2

    # Pools
    sql_mcq_pool = [
        q for q in QUESTIONS
        if q.get('type') == 'mcq' and q.get('topic', '').lower() == 'sql' and _complexity_value_local(q) in (1, 2)
    ]
    sql_practice_pool = [
        q for q in QUESTIONS
        if q.get('solution') and q.get('type') != 'mcq' and q['solution'].lower().count('join') <= 1 and _complexity_value_local(q) in (1, 2)
    ]

    random.shuffle(sql_mcq_pool)
    random.shuffle(sql_practice_pool)

    # Ensure 10 MCQ + 10 practice; if insufficient fill from the other pool (best-effort)
    selected_mcq = sql_mcq_pool[:10]
    if len(selected_mcq) < 10:
        needed = 10 - len(selected_mcq)
        selected_mcq += sql_practice_pool[:needed]
        sql_practice_pool = sql_practice_pool[needed:]

    selected_practice = sql_practice_pool[:10]
    if len(selected_practice) < 10:
        needed = 10 - len(selected_practice)
        selected_practice += [q for q in sql_mcq_pool if q not in selected_mcq][:needed]

    # Final SQL selection (best-effort to reach 20)
    selected_sql = (selected_mcq + selected_practice)[:20]

    # If we could not reach 20 SQL (very small banks), fall back to original behavior
    if len(selected_sql) < 20:
        sql_questions = [
            q for q in QUESTIONS 
            if q.get('solution') and q['solution'].lower().count('join') <= 1 
            and _complexity_value_local(q) in [1, 2]
        ]
        random.shuffle(sql_questions)
        selected_sql = sql_questions[:20]
    
    # Select 20 PowerBI questions: prefer easy (1), fill with medium (2) if needed
    def _complexity_value(q):
        c = q.get('complexity', 1)
        # accept numeric or string labels
        if isinstance(c, int):
            return c
        if isinstance(c, str):
            mapping = {'easy': 1, 'medium': 2, 'hard': 3}
            return mapping.get(c.lower(), 2)
        try:
            return int(c)
        except Exception:
            return 2

    powerbi_easy = [q for q in POWERBI_QUESTIONS if _complexity_value(q) == 1]
    powerbi_medium = [q for q in POWERBI_QUESTIONS if _complexity_value(q) == 2]
    random.shuffle(powerbi_easy)
    random.shuffle(powerbi_medium)
    selected_powerbi = powerbi_easy[:20]
    if len(selected_powerbi) < 20:
        selected_powerbi += powerbi_medium[:20 - len(selected_powerbi)]
    selected_powerbi = selected_powerbi[:20]
    
    # Combine and shuffle together
    all_questions = selected_sql + selected_powerbi
    random.shuffle(all_questions)
    
    return all_questions

# ==========================
# Streamlit App
# ==========================
st.set_page_config(
    page_title="OJT Assessment", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS with UE branding (Purple theme)
st.markdown("""
    <style>
        /* UE Color Scheme */
        :root {
            --ue-purple: #6B21A8;
            --ue-light-purple: #9D4EDD;
            --ue-dark-purple: #4C0A7A;
        }
        
        /* Main container */
        .block-container {
            padding-top: 1rem;
            padding-bottom: 0rem;
            padding-left: 2rem;
            padding-right: 2rem;
            max-width: 100%;
            background: linear-gradient(135deg, #f8f9fa 0%, #f0e6ff 100%);
        }
        
        /* Header styling */
        h1 {
            color: #6B21A8;
            font-weight: 700;
            text-align: center;
            margin-bottom: 1rem;
            text-shadow: 0 2px 4px rgba(107, 33, 168, 0.1);
        }
        
        h2, h3 {
            color: #6B21A8;
            font-weight: 600;
        }
        
        /* Buttons */
        .stButton > button {
            background-color: #6B21A8;
            color: white;
            border-radius: 8px;
            padding: 0.6rem 1.2rem;
            font-weight: 600;
            transition: all 0.3s ease;
            border: none;
        }
        
        .stButton > button:hover {
            background-color: #9D4EDD;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(107, 33, 168, 0.3);
        }
        
        /* Progress bar */
        .stProgress > div > div > div > div {
            background-color: #22C55E !important;
        }
        .stProgress > div > div > div {
            background-color: #E5E7EB !important;
        }
        
        /* Text input and text area */
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea {
            border: 2px solid #D8B4FE;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
        }
        
        .stTextInput > div > div > input:focus,
        .stTextArea > div > div > textarea:focus {
            border-color: #6B21A8;
            box-shadow: 0 0 8px rgba(107, 33, 168, 0.2);
        }
        
        /* Metrics */
        .stMetric {
            background-color: rgba(107, 33, 168, 0.05);
            padding: 1rem;
            border-radius: 8px;
            border-left: 4px solid #6B21A8;
        }
        
        /* Expander */
        .streamlit-expanderContent {
            background-color: rgba(157, 78, 221, 0.05);
            border-radius: 8px;
            border: 1px solid #D8B4FE;
        }
        
        /* Success/Error messages */
        .stSuccess {
            background-color: rgba(34, 197, 94, 0.1);
            border-left: 4px solid #22C55E;
        }
        
        .stError {
            background-color: rgba(239, 68, 68, 0.1);
            border-left: 4px solid #EF4444;
        }
        
        .stWarning {
            background-color: rgba(251, 146, 60, 0.1);
            border-left: 4px solid #FB923C;
        }
        
        /* Dataframe */
        .stDataFrame {
            border: 1px solid #D8B4FE;
            border-radius: 8px;
        }
        
        /* Reduce spacing between elements */
        div[data-testid="stVerticalBlock"] > div {
            margin-bottom: 0.5rem;
        }
        
        /* Make text area more compact */
        .stTextArea textarea {
            font-size: 13px;
            font-family: 'Courier New', monospace;
        }
        
        /* Reduce header spacing */
        h1, h2, h3 {
            margin-bottom: 0.5rem;
            margin-top: 0.5rem;
        }
        
        /* Compact buttons */
        .stButton > button {
            width: 100%;
            padding: 0.5rem;
        }
        
        /* Reduce expander padding */
        .streamlit-expanderContent {
            padding: 0.5rem 1rem;
        }
        
        /* Compact metric display */
        .stMetric {
            background-color: transparent;
            padding: 0.5rem;
        }
        
        /* Sidebar styling */
        [data-testid="stSidebar"] {
            background-color: #f8f9fa;
            border-right: 2px solid #D8B4FE;
        }
        
        /* Logo container */
        .logo-container {
            text-align: center;
            padding: 1rem 0;
            margin-bottom: 1rem;
            border-bottom: 2px solid #D8B4FE;
        }
        
        .logo-text {
            color: #6B21A8;
            font-weight: 700;
            font-size: 24px;
            margin-top: 0.5rem;
        }
        
        /* Hide GitHub icon (top-right) */
        header [data-testid="stGithubLink"] {
            display: none;
        }
        
        /* Optional: hide entire Streamlit header bar */
        header {
            visibility: hidden;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown("---")

# Initialize session state
if "current_q" not in st.session_state:
    st.session_state.current_q = 0
if "answers" not in st.session_state:
    st.session_state.answers = []
if "show_feedback" not in st.session_state:
    st.session_state.show_feedback = False
if "feedback_correct" not in st.session_state:
    st.session_state.feedback_correct = False
if "feedback_message" not in st.session_state:
    st.session_state.feedback_message = ""
if "user_sql_input" not in st.session_state:
    st.session_state.user_sql_input = ""
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False
if "shuffled_questions" not in st.session_state:
    st.session_state.shuffled_questions = None
if "current_user_name" not in st.session_state:
    st.session_state.current_user_name = None

# Ensure required runtime directories exist and are correctly mapped to this module
SUBMISSIONS_DIR = os.path.join(os.path.dirname(__file__), "submissions")
if not os.path.exists(SUBMISSIONS_DIR):
    try:
        os.makedirs(SUBMISSIONS_DIR, exist_ok=True)
    except Exception:
        # If we cannot create the directory, admin UI will report issues later — keep going
        pass
# Add .gitkeep so repo keeps the directory (if nothing else is present)
gitkeep = os.path.join(SUBMISSIONS_DIR, ".gitkeep")
if not os.path.exists(gitkeep):
    try:
        open(gitkeep, "a").close()
    except Exception:
        pass

# ==========================
# Admin Mode Check - Show at Top
# ==========================
# Create a sidebar for admin access
with st.sidebar:
    st.subheader("🔐 Admin Access")
    
    if not st.session_state.admin_authenticated:
        admin_password = st.text_input("Enter Admin Password:", type="password", key="admin_password_sidebar")
        if st.button("🔓 Login as Admin", key="admin_login_btn", use_container_width=True):
            if admin_password == "admin123":  # Change this to a secure password
                st.session_state.admin_authenticated = True
                st.success("✅ Admin access granted!")
                st.rerun()
            else:
                st.error("❌ Incorrect password.")
    else:
        st.success("✅ Admin Mode Active")
        if st.button("🔒 Logout Admin", key="admin_logout_btn", use_container_width=True):
            st.session_state.admin_authenticated = False
            st.rerun()

# Admin dashboard title handled below
if st.session_state.admin_authenticated:
    pass

# Update title with styling
if st.session_state.admin_authenticated:
    st.markdown("<h1 style='color: #EF4444; text-align: center;'>🔴 ADMIN MODE - Training Management</h1>", unsafe_allow_html=True)
else:
    st.markdown("")  # Empty line for spacing

# ==========================
# Admin Dashboard Section (Always Available to Authenticated Admins)
# ==========================
if st.session_state.admin_authenticated:
    st.warning("⚠️ You are in ADMIN MODE - Viewing all OJT assessment submissions")
    st.divider()
    st.markdown("<h2 style='color: #6B21A8; text-align: center;'>📊 OJT Assessment Dashboard</h2>", unsafe_allow_html=True)
    
    # Create submissions folder if it doesn't exist
    submissions_dir = os.path.join(os.path.dirname(__file__), 'submissions')
    if not os.path.exists(submissions_dir):
        os.makedirs(submissions_dir)
    
    # Read all submission files
    submission_files = [f for f in os.listdir(submissions_dir) if f.endswith('.csv')]
    
    if submission_files:
        st.info(f"✅ Total employee submissions: {len(submission_files)}")
        
        # Load and aggregate all submissions
        all_details = []
        summary_rows = []
        
        for file in submission_files:
            # ignore temporary/partial in-flight files
            if file.endswith('.tmp') or file.endswith('.lock'):
                continue
            file_path = os.path.join(submissions_dir, file)
            try:
                # skip zero-length / likely partial files
                if os.path.getsize(file_path) == 0:
                    continue
                df = pd.read_csv(file_path)

                # Extract metadata robustly
                name = None
                email = None
                if len(df) > 0:
                    # prefer explicit columns
                    name = df.iloc[0].get('Name') if 'Name' in df.columns else None
                    email = df.iloc[0].get('Email') if 'Email' in df.columns else None

                # fallback: try to read a SUMMARY row or infer from filename
                if not name or not email:
                    # look for SUMMARY row
                    if 'question_id' in df.columns and any(df['question_id'] == 'SUMMARY'):
                        row = df[df['question_id'] == 'SUMMARY'].iloc[0]
                        name = name or row.get('Name')
                        email = email or row.get('Email')

                if not name:
                    # infer from filename pattern (robust) or from any cell that looks like an email
                    try:
                        # 1) filename patterns like alice_at_company_com_2026... or alice@example.com-like
                        m = re.search(r"([A-Za-z0-9._%+-]+_at_[A-Za-z0-9._%+-]+)", file)
                        if m:
                            candidate = m.group(1)
                            # strip trailing date-like suffixes if present (e.g. _20260203_000000)
                            candidate = re.sub(r'(_\d{6,16}.*)$', '', candidate)
                            email = email or candidate.replace('_at_', '@').replace('_', '.')
                        else:
                            # try dot-separated fallback
                            m2 = re.search(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", file)
                            if m2:
                                email = email or m2.group(1)
                    except Exception:
                        pass

                # 2) scan the dataframe for any cell that looks like a name/email
                if (not name or not email) and len(df) > 0:
                    try:
                        for col in df.columns:
                            # examine first few non-null values
                            for v in df[col].astype(str).head(10).values:
                                if not name and v and len(v.strip()) > 0 and not re.search(r"\d", v):
                                    # heuristic: treat longer text without digits as a possible name
                                    if len(v.strip()) > 2 and len(v.split()) <= 4 and any(c.isalpha() for c in v):
                                        name = name or v.strip()
                                if not email and '@' in v:
                                    # accept raw emails
                                    em = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", v)
                                    if em:
                                        email = email or em.group(0)
                    except Exception:
                        pass

                name = (name or 'Unknown')
                email = (email or 'Unknown')

                # Count correct answers robustly
                if 'is_correct' in df.columns:
                    correct_count = int(df['is_correct'].sum())
                else:
                    # try Best-effort: look for 'Correct Answers' summary column
                    correct_count = int(df.iloc[0].get('Correct Answers', 0))

                total_count = int(df.iloc[0].get('Total Questions', len(df))) if len(df) > 0 else 0
                score_pct = (correct_count / total_count * 100) if total_count > 0 else 0

                # Create summary for this user
                summary_rows.append({
                    "Name": name,
                    "Email": email,
                    "Correct Answers": int(correct_count),
                    "Total Questions": total_count,
                    "Score (%)": f"{score_pct:.1f}",
                    "Submitted At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

                # Add detailed rows for later viewing
                all_details.append((name, email, df))
            except Exception as e:
                st.warning(f"Error reading {file}: {e}")
        
        if summary_rows:
            summary_df = pd.DataFrame(summary_rows)
            
            # Display summary table
            st.subheader("Employee Assessment Summary")
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
            
            # Export options
            st.subheader(" Export Options")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Export as CSV
                csv_data = summary_df.to_csv(index=False)
                st.download_button(
                    label=" Download Summary as CSV",
                    data=csv_data,
                    file_name=f"sql_assessment_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            
            with col2:
                # Export as Excel
                try:
                    import openpyxl
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        summary_df.to_excel(writer, index=False, sheet_name='Summary')
                    excel_buffer.seek(0)
                    st.download_button(
                        label=" Download Summary as Excel",
                        data=excel_buffer.getvalue(),
                        file_name=f"sql_assessment_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                except ImportError:
                    st.info("Install openpyxl: pip install openpyxl")
            
            with col3:
                st.metric("Total Users", len(summary_df))
            
            # Summary statistics
            st.subheader(" Summary Statistics")
            stats_col1, stats_col2, stats_col3, stats_col4 = st.columns(4)
            
            with stats_col1:
                st.metric("Total Submissions", len(summary_df))
            
            with stats_col2:
                avg_correct = pd.to_numeric(summary_df['Correct Answers']).mean()
                st.metric("Avg Correct Answers", f"{avg_correct:.1f}")
            
            with stats_col3:
                avg_score = pd.to_numeric(summary_df['Score (%)'].astype(str)).mean()
                st.metric("Avg Score", f"{avg_score:.1f}%")
            
            with stats_col4:
                st.metric("Unique Users", len(summary_df))
            
            # Detailed view option
            with st.expander(" View Detailed Answers by User"):
                for name, email, detail_df in all_details:
                    st.markdown(f"### {name} ({email})")

                    # Defensive handling for multiple submission CSV schemas:
                    # - preferred: per-question rows with 'is_correct' column
                    # - summary: single-row CSV with 'Correct Answers' and 'Total Questions'
                    # - legacy/partial: per-question rows with 'your_answer' + 'correct_answer' (no 'is_correct')
                    if 'is_correct' in detail_df.columns:
                        correct_count = int(detail_df['is_correct'].sum())
                        total_count = len(detail_df)
                        display_df = detail_df[['question_id', 'question', 'type', 'your_answer', 'correct_answer', 'is_correct']].copy()
                        display_df.columns = ['Q#', 'Question', 'Type', 'Your Answer', 'Correct Answer', 'Correct']

                    elif 'Correct Answers' in detail_df.columns and 'Total Questions' in detail_df.columns:
                        # summary-style CSV produced by older/alternate exporters
                        try:
                            correct_count = int(pd.to_numeric(detail_df['Correct Answers']).iloc[0])
                        except Exception:
                            correct_count = 0
                        try:
                            total_count = int(pd.to_numeric(detail_df['Total Questions']).iloc[0])
                        except Exception:
                            total_count = max(0, int(len(detail_df)))
                        display_df = pd.DataFrame([{
                            'Q#': 'SUMMARY', 'Question': '', 'Type': '', 'Your Answer': '', 'Correct Answer': '', 'Correct': ''
                        }])

                    elif 'your_answer' in detail_df.columns and 'correct_answer' in detail_df.columns:
                        # infer correctness when explicit column missing
                        tmp = detail_df.copy()
                        tmp['is_correct'] = tmp['your_answer'].astype(str) == tmp['correct_answer'].astype(str)
                        correct_count = int(tmp['is_correct'].sum())
                        total_count = len(tmp)
                        display_df = tmp[['question_id', 'question', 'type', 'your_answer', 'correct_answer', 'is_correct']].copy()
                        display_df.columns = ['Q#', 'Question', 'Type', 'Your Answer', 'Correct Answer', 'Correct']

                    else:
                        # Unknown schema — show best-effort summary without raising
                        correct_count = 0
                        total_count = len(detail_df)
                        display_df = pd.DataFrame(columns=['Q#', 'Question', 'Type', 'Your Answer', 'Correct Answer', 'Correct'])

                    score_pct = (correct_count / total_count * 100) if total_count > 0 else 0
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Score", f"{score_pct:.1f}%")
                    with col2:
                        st.metric("Correct", f"{correct_count}/{total_count}")
                    with col3:
                        st.metric("Questions", total_count)

                    # Show detailed answers (may be empty for summary/unknown schemas)
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    st.divider()
        
    else:
        st.info(" No submissions yet. Employees can complete the assessment to generate reports.")
    
    # Stop here - don't show student assessment
    st.stop()

# ==========================
# Student Assessment Section (Only if not in Admin Mode)
# ==========================
st.markdown("<h2 style='color: #6B21A8; text-align: center;'>👨‍💼 OJT Assessment</h2>", unsafe_allow_html=True)
# Subheader removed per request (previously: "Complete 34 comprehensive SQL proficiency questions")
st.divider()

st.markdown("**👤 Employee Information** (Required)")
col_name, col_email = st.columns(2)
with col_name:
    student_name = st.text_input("Your Full Name", key="student_name", placeholder="Enter your full name")
with col_email:
    student_email = st.text_input("Company Email", key="student_email", placeholder="Enter your company email")

# Validate mandatory fields
if not student_name or not student_email:
    st.warning(" Please enter both your name and email to begin the assessment.")
    st.stop()

# Initialize shuffled questions for this user if not already done or if user changed
if st.session_state.shuffled_questions is None or st.session_state.current_user_name != student_name:
    st.session_state.shuffled_questions = get_shuffled_questions(student_name)
    st.session_state.current_user_name = student_name
    st.session_state.current_q = 0
    st.session_state.answers = []

# Progress bar (defensive)
if not st.session_state.shuffled_questions:
    st.error("No questions available.")
    st.session_state.show_results = True
else:
    # Clamp current_q into the valid index range and compute progress
    st.session_state.current_q = min(st.session_state.current_q, max(0, len(st.session_state.shuffled_questions) - 1))
    progress = min((st.session_state.current_q + 1) / len(st.session_state.shuffled_questions), 1.0)
    st.progress(progress)
    st.subheader(f"Question {st.session_state.current_q + 1} of {len(st.session_state.shuffled_questions)}")
    q = st.session_state.shuffled_questions[st.session_state.current_q]
    st.markdown(f"**Question:** {q['question']}")

# Display description and table information (if available) — hidden for MCQ questions
if q.get("type") != "mcq":
    with st.expander(" Question Details & Schema"):
        if 'description' in q:
            st.markdown(f"**Description:** {q['description']}")
        else:
            st.markdown("**Description:** _(No description available for this question)_")
        if 'table_info' in q:
            st.markdown("**Tables Involved:**")
            for table_name, table_data in q['table_info'].items():
                st.markdown(f"- **{table_name}**")
                if isinstance(table_data, dict):
                    if 'columns' in table_data:
                        st.write(f"  Columns: {', '.join(table_data['columns'])}")
                    if 'sample' in table_data:
                        st.markdown("  **Sample Data:**")
                        parsed = parse_sample_text(table_data['sample'])
                        if parsed['type'] == 'io':
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown("**Input:**")
                                st.code(parsed['input'])
                            with col2:
                                st.markdown("**Output:**")
                                st.code(parsed['output'])
                        elif parsed['type'] == 'kv':
                            st.dataframe(parsed['rows'], width='stretch', hide_index=True)
                        else:
                            st.write(f"  {parsed['text']}")
                    else:
                        st.markdown("**Tables Involved:** _(Not applicable for this question)_")
                if 'relationship' in table_data:
                    st.write(f"  Relationship: {table_data['relationship']}")
    
        # Show relationship info if available
        if 'relationship' in q.get('table_info', {}):
            st.markdown(f"**Relationship:** {q['table_info']['relationship']}")

# Determine question type and display accordingly
if q.get("type") == "mcq":
    # PowerBI MCQ Question
    st.markdown("### Multiple Choice Question")
    
    # Display options
    selected_options = []
    is_multiselect = len(q["correct_answers"]) > 1
    
    # Prepare lock/view flags for this question
    lock_key = f"locked_{q['id']}"
    view_key = f"viewed_solution_{q['id']}"
    submitted_key = f"submitted_{q['id']}"
    if lock_key not in st.session_state:
        st.session_state[lock_key] = False
    if view_key not in st.session_state:
        st.session_state[view_key] = False
    if submitted_key not in st.session_state:
        st.session_state[submitted_key] = False

    if is_multiselect:
        st.info("⚠️ Select all that apply")
        for option in q["options"]:
            if st.checkbox(option, key=f"option_{st.session_state.current_q}_{option}", disabled=st.session_state[lock_key]):
                # Extract letter (A, B, C, D)
                letter = option.split(".")[0].strip()
                selected_options.append(letter)
    else:
        # Use a placeholder first option so no real answer is pre-selected
        placeholder = "Choose..."
        options_with_placeholder = [placeholder] + q["options"]
        selected_option = st.radio("Select the correct answer:", options_with_placeholder, index=0, key=f"option_{st.session_state.current_q}")
        if selected_option and selected_option != placeholder:
            letter = selected_option.split(".")[0].strip()
            selected_options = [letter]
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("Submit Answer", type="primary", key=f"submit_mcq_{st.session_state.current_q}", disabled=(st.session_state[lock_key] or st.session_state[submitted_key])):
            if not selected_options:
                st.warning("Please select an answer before submitting.")
            else:
                # Check if selected answers match correct answers
                correct = set(selected_options) == set(q["correct_answers"])
                
                # Store answer (include Name/Email in the saved payload)
                st.session_state.answers.append({
                    "Name": st.session_state.get('student_name', ''),
                    "Email": st.session_state.get('student_email', ''),
                    "question_id": q["id"],
                    "question": q["question"],
                    "your_answer": ", ".join(selected_options),
                    "correct_answer": ", ".join(q["correct_answers"]),
                    "is_correct": correct,
                    "type": "mcq"
                })
                # Auto-save answers after each submission (include Name/Email so admin can identify partials)
                import pandas as pd
                import os
                user_email = st.session_state.get('student_email', 'unknown').replace('@', '_at_').replace('.', '_')
                save_dir = os.path.join(os.path.dirname(__file__), 'submissions')
                os.makedirs(save_dir, exist_ok=True)
                save_path = os.path.join(save_dir, f"{user_email}_partial.csv")
                df = pd.DataFrame(st.session_state.answers)
                # atomic write
                tmp_path = save_path + '.tmp'
                df.to_csv(tmp_path, index=False)
                os.replace(tmp_path, save_path)
                
                # Show feedback
                st.session_state.show_feedback = True
                st.session_state.feedback_correct = correct
                if correct:
                    st.session_state.feedback_message = "✅ Correct!"
                else:
                    st.session_state.feedback_message = "❌ Incorrect."
                # mark as submitted to prevent re-submission
                st.session_state[submitted_key] = True
    
    with col2:
        if st.session_state.current_q + 1 < len(st.session_state.shuffled_questions):
            if st.button("Next Question", disabled=not st.session_state.show_feedback, key=f"next_mcq_{st.session_state.current_q}"):
                st.session_state.current_q += 1
                st.session_state.show_feedback = False
                st.session_state.user_sql_input = ""
                st.rerun()
        else:
            if st.button("Show Results", disabled=not st.session_state.show_feedback, key=f"results_mcq_{st.session_state.current_q}"):
                st.session_state.show_feedback = False
                # clamp to last valid index and mark that results should be shown
                st.session_state.current_q = max(0, len(st.session_state.shuffled_questions) - 1)
                st.session_state.show_results = True
    
    # Show feedback for MCQ
    if st.session_state.show_feedback:
        if st.session_state.feedback_correct:
            st.success(st.session_state.feedback_message)
        else:
            st.error(st.session_state.feedback_message)
            # Let the user explicitly view the correct answer — once viewed the question is locked
            if not st.session_state[view_key]:
                if st.button("View correct answer", key=f"view_mcq_{st.session_state.current_q}"):
                    st.session_state[view_key] = True
                    st.session_state[lock_key] = True

            if st.session_state[view_key]:
                st.markdown(f"**Correct Answer(s):** {', '.join(q['correct_answers'])}")
                st.markdown("**Your Answer(s):** " + st.session_state.answers[-1]['your_answer'])
                # Edit allowed only if not locked (locked becomes True when user views the solution)
                if not st.session_state[lock_key]:
                    if st.button("Edit Answer", key=f"edit_mcq_{st.session_state.current_q}"):
                        # Remove stored answer for this question and reset option states
                        for i in range(len(st.session_state.answers) - 1, -1, -1):
                            if st.session_state.answers[i]["question_id"] == q["id"]:
                                st.session_state.answers.pop(i)
                                break
                        # Reset option widgets for this question
                        for option in q["options"]:
                            key = f"option_{st.session_state.current_q}_{option}"
                            if key in st.session_state:
                                st.session_state[key] = False
                        st.session_state.show_feedback = False
                        st.session_state.feedback_message = ""
                        # allow re-submission after editing
                        st.session_state[submitted_key] = False
                        st.rerun()
else:
    # SQL Question
    user_sql = st.text_area(
        "Enter your SQL query here:", 
        height=120,
        value=st.session_state.user_sql_input,
        key=f"sql_input_{st.session_state.current_q}"
    )
    
    col1, col2 = st.columns([1, 1])
    
    # Prepare lock/view flags for this question
    lock_key = f"locked_{q['id']}"
    view_key = f"viewed_solution_{q['id']}"
    submitted_key = f"submitted_{q['id']}"
    if lock_key not in st.session_state:
        st.session_state[lock_key] = False
    if view_key not in st.session_state:
        st.session_state[view_key] = False
    if submitted_key not in st.session_state:
        st.session_state[submitted_key] = False

    with col1:
        if st.button("Submit Answer", type="primary", key=f"submit_sql_{st.session_state.current_q}", disabled=(st.session_state[lock_key] or st.session_state[submitted_key])):
            if not user_sql.strip():
                st.warning("Please enter an answer before submitting.")
            else:
                # Normalize & compare
                normalized_candidate = normalize_sql(user_sql)
                normalized_solution = normalize_sql(q["solution"])
                
                correct = normalized_candidate == normalized_solution
                
                # Store answer (include Name/Email in the saved payload)
                st.session_state.answers.append({
                    "Name": st.session_state.get('student_name', ''),
                    "Email": st.session_state.get('student_email', ''),
                    "question_id": q["id"],
                    "question": q["question"],
                    "your_answer": user_sql,
                    "correct_answer": q["solution"],
                    "is_correct": correct,
                    "type": "sql"
                })
                # Auto-save answers after each submission (include Name/Email so admin can identify partials)
                import pandas as pd
                import os
                user_email = st.session_state.get('student_email', 'unknown').replace('@', '_at_').replace('.', '_')
                save_dir = os.path.join(os.path.dirname(__file__), 'submissions')
                os.makedirs(save_dir, exist_ok=True)
                save_path = os.path.join(save_dir, f"{user_email}_partial.csv")
                df = pd.DataFrame(st.session_state.answers)
                # atomic write
                tmp_path = save_path + '.tmp'
                df.to_csv(tmp_path, index=False)
                os.replace(tmp_path, save_path)
                
                # Show feedback
                st.session_state.show_feedback = True
                st.session_state.feedback_correct = correct
                if correct:
                    st.session_state.feedback_message = "✅ Correct!"
                else:
                    st.session_state.feedback_message = "❌ Incorrect."
                # mark as submitted to prevent re-submission
                st.session_state[submitted_key] = True
    
    with col2:
        if st.session_state.current_q + 1 < len(st.session_state.shuffled_questions):
            if st.button("Next Question", disabled=not st.session_state.show_feedback, key=f"next_sql_{st.session_state.current_q}"):
                st.session_state.current_q += 1
                st.session_state.show_feedback = False
                st.session_state.user_sql_input = ""
                st.rerun()
        else:
            if st.button("Show Results", disabled=not st.session_state.show_feedback, key=f"results_sql_{st.session_state.current_q}"):
                st.session_state.show_feedback = False
                # clamp to last valid index and mark that results should be shown
                st.session_state.current_q = max(0, len(st.session_state.shuffled_questions) - 1)
                st.session_state.show_results = True
    
    # Show feedback for SQL
    if st.session_state.show_feedback:
        if st.session_state.feedback_correct:
            st.success(st.session_state.feedback_message)
        else:
            st.error(st.session_state.feedback_message)
            # Let the user explicitly view the solution — once viewed the question is locked
            if not st.session_state[view_key]:
                if st.button("View solution", key=f"view_sql_{st.session_state.current_q}"):
                    st.session_state[view_key] = True
                    st.session_state[lock_key] = True

            if st.session_state[view_key]:
                st.code(q["solution"], language="sql")
                st.markdown("**Explanation:**")
                st.write(f"Your answer: `{st.session_state.answers[-1]['your_answer']}`")
                # Edit allowed only if not locked
                if not st.session_state[lock_key]:
                    if st.button("Edit Answer", key=f"edit_sql_{st.session_state.current_q}"):
                        # Restore last submitted SQL for re-editing and remove stored submission
                        for i in range(len(st.session_state.answers) - 1, -1, -1):
                            if st.session_state.answers[i]["question_id"] == q["id"]:
                                st.session_state.user_sql_input = st.session_state.answers[i]["your_answer"]
                                st.session_state.answers.pop(i)
                                break
                        st.session_state.show_feedback = False
                        st.session_state.feedback_message = ""
                        # allow re-submission after editing
                        st.session_state[submitted_key] = False
                        st.rerun()

# Show results when all questions are completed
if (st.session_state.current_q >= len(st.session_state.shuffled_questions) or 
    (len(st.session_state.answers) >= len(st.session_state.shuffled_questions) and st.session_state.current_q == len(st.session_state.shuffled_questions) - 1)):
    
    st.success(" You have completed all questions!")
    
    # Show summary
    st.subheader("📈 Your Training Assessment Results")
    total = len(st.session_state.answers)
    correct_count = sum(a["is_correct"] for a in st.session_state.answers)
    score_percentage = (correct_count / total) * 100
    
    # Display score with color coding
    if score_percentage >= 80:
        st.success(f"� You've completed the assessment! - Score: {correct_count}/{total} ({score_percentage:.1f}%)")
    elif score_percentage >= 60:
        st.success(f"🎉 You've completed the assessment! - Score: {correct_count}/{total} ({score_percentage:.1f}%)")
    else:
        st.success(f"🎉 You've completed the assessment! - Score: {correct_count}/{total} ({score_percentage:.1f}%)")
    
    st.metric("Your Score", f"{correct_count}/{total} ({score_percentage:.1f}%)")
    
    # Save submission to CSV
    # Always use the latest values from the input fields for name/email
    student_name_final = st.session_state.get('student_name', student_name)
    student_email_final = st.session_state.get('student_email', student_email)
    if student_name_final and student_email_final:
        if not os.path.exists("submissions"):
            os.makedirs("submissions")
        
        # Get current submission datetime and ensure unique filename for concurrent submissions
        submission_datetime = datetime.now()
        import uuid
        unique_suffix = submission_datetime.strftime('%Y%m%d_%H%M%S_%f') + '_' + uuid.uuid4().hex[:8]
        
        # Create submission data (guarantee Name/Email present)
        submission_data = {
            "Name": student_name_final or student_name,
            "Email": student_email_final or student_email,
            "Submitted At": submission_datetime.strftime("%Y-%m-%d %H:%M:%S.%f"),
            "Total Questions": total,
            "Correct Answers": correct_count,
            "Score (%)": round(score_percentage, 2)
        }
        
        # Add individual question results
        for i, ans in enumerate(st.session_state.answers):
            submission_data[f"Q{ans['question_id']}_Answer"] = ans.get('is_correct')
        
        # Save to submissions folder with unique filename (atomic)
        os.makedirs('submissions', exist_ok=True)
        submission_file = f"submissions/{(student_email_final or student_email).replace('@','_at_').replace('.','_')}_{unique_suffix}.csv"
        submission_df = pd.DataFrame([submission_data])
        tmp_file = submission_file + '.tmp'
        submission_df.to_csv(tmp_file, index=False)
        os.replace(tmp_file, submission_file)
        st.success(f"✅ Your results have been saved! (Submitted: {submission_datetime.strftime('%Y-%m-%d %H:%M:%S')})")
    
    # Detailed results
    with st.expander("View Detailed Results"):
        for i, ans in enumerate(st.session_state.answers):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**Q{ans['question_id']}: {ans['question']}**")
                if ans.get("type") == "mcq":
                    st.markdown(f"- Your Answer(s): **{ans['your_answer']}**")
                    st.markdown(f"- Correct Answer(s): **{ans['correct_answer']}**")
                else:
                    st.markdown(f"- Your Answer: `{ans['your_answer']}`")
                    st.markdown(f"- Correct Answer: `{ans['correct_answer']}`")
            with col2:
                if ans['is_correct']:
                    st.success("✅ Correct")
                else:
                    st.error("❌ Incorrect")
            st.divider()
    

    # ==========================
    # Footer (Only on Results)
    # ==========================
    st.divider()
    st.markdown("""
        <div style='text-align: center; padding: 2rem; background: linear-gradient(135deg, rgba(107, 33, 168, 0.05) 0%, rgba(157, 78, 221, 0.05) 100%); border-radius: 8px; margin-top: 2rem;'>
            <p style='color: #6B21A8; font-weight: 600; margin: 0;'>OJT Assessment Platform</p>
            <p style='color: #757575; font-size: 13px; margin: 0.5rem 0 0 0;'>OJT Assessment Program for Employee Training</p>
            <p style='color: #A78BFA; font-size: 11px; margin: 1rem 0 0 0;'>© 2026 OJT Assessment. All rights reserved.</p>
        </div>
    """, unsafe_allow_html=True)
