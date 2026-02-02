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

# ==========================
# SQL Question Bank with Enhanced Information
# ==========================
QUESTIONS = [
    {
        "id":1, 
        "question":"Which shippers do we have?", 
        "description": "Display all shipping companies available in the database. This helps identify all carriers used for order deliveries.",
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
        "description": "Extract specific information about product categories. Show the category name and its description to understand product groupings.",
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
        "description": "List all employees who work as Sales Representatives. Display their names and when they were hired to track the sales team.",
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
        "description": "Filter sales representatives by country. Identify the US-based sales team for regional management purposes.",
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
        "description": "Retrieve all orders handled by a particular employee (ID 5). Used to track individual sales performance and order history.",
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
        "description": "Find suppliers excluding Marketing Managers. Useful for identifying decision makers and procurement contacts at different supplier organizations.",
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
        "description": "Search for products containing 'queso' in their name. Demonstrates pattern matching for product discovery and inventory management.",
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
        "description": "Find orders going to specific European countries. Useful for regional shipping analysis and logistics planning.",
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
        "description": "Filter orders by multiple countries using IN clause. Demonstrates grouping multiple conditions for regional analysis.",
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
        "description": "Sort employees by birthdate to identify age demographics and workforce composition. Shows sorting in ascending order.",
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
        "description": "Extract just the date portion from a datetime field. Demonstrates data type casting and formatting for readability.",
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
        "description": "Connect orders with shipping companies to see which carrier was used. Demonstrates JOIN with date formatting.",
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
        "tables": ["customers", "orders", "orderdetails"],
        "table_info": {
            "customers": {"columns": ["customerid (VARCHAR, PK)", "companyname (VARCHAR)"]},
            "orders": {"columns": ["orderid (INT, PK)", "customerid (VARCHAR, FK)", "orderdate (DATE)"]},
            "orderdetails": {"columns": ["orderid (INT, FK)", "quantity (INT)", "unitprice (DECIMAL)", "discount (DECIMAL)"]},
            "relationship": "Calculate: total = SUM(quantity * unitprice * (1 - discount))"
        },
        "solution":"SELECT c.customerid, c.companyname, SUM(od.quantity * od.unitprice) AS totalswithoutdiscount, SUM(od.quantity * od.unitprice * (1 - discount)) AS totalswithdiscount FROM customers AS c JOIN orders AS o ON o.customerid = c.customerid JOIN orderdetails AS od ON o.orderid = od.orderid WHERE orderdate >= '20160101' AND orderdate < '20170101' GROUP BY c.customerid, c.companyname HAVING SUM(od.quantity * od.unitprice * (1 - discount)) > 10000 ORDER BY totalswithdiscount DESC"
    }
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
    - Returns 20 SQL questions + 20 PowerBI questions (40 total)
    - Uses user's name as seed for consistent randomization
    """
    # Create a hash seed from the user's name
    seed = int(hashlib.md5(user_name.lower().encode()).hexdigest(), 16)
    random.seed(seed)
    
    # Select 20 SQL questions (balance by complexity)
    sql_questions = list(QUESTIONS)
    random.shuffle(sql_questions)
    selected_sql = sql_questions[:20]
    
    # Select 20 PowerBI questions (balance by complexity)
    powerbi_questions = list(POWERBI_QUESTIONS)
    random.shuffle(powerbi_questions)
    selected_powerbi = powerbi_questions[:20]
    
    # Combine and shuffle together
    all_questions = selected_sql + selected_powerbi
    random.shuffle(all_questions)
    
    return all_questions

# ==========================
# Streamlit App
# ==========================
st.set_page_config(
    page_title="SQL Assessment - Employee Training", 
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

# ==========================
# UE Branding Header
# ==========================
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    # Display logo
    try:
        # Try to display logo, show placeholder if missing
        import pathlib
        logo_path = "We_logo.svg695283768.png"
        if pathlib.Path(logo_path).exists():
            st.image(logo_path, width=100)
        else:
            st.warning("Logo not found. Please add 'We_logo.svg695283768.png' to the project directory.")
    except:
        pass

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
    st.warning("⚠️ You are in ADMIN MODE - Viewing all employee training submissions")
    st.divider()
    st.markdown("<h2 style='color: #6B21A8; text-align: center;'>📊 Employee Training Assessment Dashboard</h2>", unsafe_allow_html=True)
    
    # Create submissions folder if it doesn't exist
    if not os.path.exists("submissions"):
        os.makedirs("submissions")
    
    # Read all submission files
    submission_files = [f for f in os.listdir("submissions") if f.endswith('.csv')]
    
    if submission_files:
        st.info(f"✅ Total employee submissions: {len(submission_files)}")
        
        # Load all submissions and pad missing Qx_Answer columns
        all_submissions = []
        num_questions = 34
        answer_cols = [f"Q{i}_Answer" for i in range(1, num_questions+1)]
        for file in submission_files:
            try:
                df = pd.read_csv(f"submissions/{file}")
                # Pad missing Qx_Answer columns with empty or default values
                for col in answer_cols:
                    if col not in df.columns:
                        df[col] = ''
                # Ensure columns are in the correct order
                base_cols = [c for c in df.columns if not c.startswith('Q')]
                df = df[base_cols + answer_cols]
                all_submissions.append(df)
            except Exception as e:
                st.warning(f"Error reading {file}: {e}")
        
        if all_submissions:
            # Keep a copy of the original (string) DataFrame for export
            all_submissions_export = [df.copy() for df in all_submissions]
            # Normalize Qx_Answer columns to boolean (True/False) and replace None with False for display only
            for df in all_submissions:
                for col in answer_cols:
                    if col in df.columns:
                        df[col] = df[col].map(lambda x: True if str(x).strip().lower() == 'true' else (False if str(x).strip().lower() == 'false' else False))
            # Combine all submissions for display
            combined_df = pd.concat(all_submissions, ignore_index=True)
            # Combine all submissions for export (original values)
            combined_df_export = pd.concat(all_submissions_export, ignore_index=True)
            
            # Display submissions table
            st.subheader("All Employee Submissions")
            st.dataframe(combined_df, use_container_width=True, hide_index=True)
            
            # Export options
            st.subheader(" Export Options")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Export as CSV
                csv_data = combined_df_export.to_csv(index=False)
                st.download_button(
                    label=" Download as CSV",
                    data=csv_data,
                    file_name=f"sql_assessment_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            
            with col2:
                # Export as Excel
                try:
                    import openpyxl
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        combined_df.to_excel(writer, index=False, sheet_name='Submissions')
                    excel_buffer.seek(0)
                    st.download_button(
                        label=" Download as Excel",
                        data=excel_buffer.getvalue(),
                        file_name=f"sql_assessment_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                except ImportError:
                    st.info("Install openpyxl: pip install openpyxl")
            
            with col3:
                st.metric("Total Users", len(combined_df))
            
            # Summary statistics
            st.subheader(" Summary Statistics")
            stats_col1, stats_col2, stats_col3, stats_col4 = st.columns(4)
            
            with stats_col1:
                st.metric("Total Submissions", len(combined_df))
            
            with stats_col2:
                if 'Correct Answers' in combined_df.columns:
                    avg_correct = combined_df['Correct Answers'].mean()
                    st.metric("Avg Correct Answers", f"{avg_correct:.1f}")
            
            with stats_col3:
                if 'Score (%)' in combined_df.columns:
                    avg_score = combined_df['Score (%)'].mean()
                    st.metric("Avg Score", f"{avg_score:.1f}%")
            
            with stats_col4:
                st.metric("Unique Users", combined_df['Name'].nunique() if 'Name' in combined_df.columns else 'N/A')
            
            # Detailed view option
            with st.expander(" View Detailed Submissions"):
                for idx, row in combined_df.iterrows():
                    st.markdown(f"### {row['Name']} ({row['Email']})")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Score", f"{row['Score (%)']}%")
                    with col2:
                        st.metric("Correct", f"{row['Correct Answers']}/{row['Total Questions']}")
                    with col3:
                        st.metric("Submitted", row['Submitted At'])
                    st.divider()
        
    else:
        st.info(" No submissions yet. Employees can complete the assessment to generate reports.")
    
    # Stop here - don't show student assessment
    st.stop()

# ==========================
# Student Assessment Section (Only if not in Admin Mode)
# ==========================
st.markdown("<h2 style='color: #6B21A8; text-align: center;'>👨‍💼 Employee SQL Training Assessment</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #757575;'>Complete 34 comprehensive SQL proficiency questions</p>", unsafe_allow_html=True)
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

# Progress bar
progress = min((st.session_state.current_q + 1) / len(st.session_state.shuffled_questions), 1.0)
st.progress(progress)
st.subheader(f"Question {st.session_state.current_q + 1} of {len(st.session_state.shuffled_questions)}")

q = st.session_state.shuffled_questions[st.session_state.current_q]
st.markdown(f"**Question:** {q['question']}")

# Display description and table information
with st.expander(" Question Details & Schema"):
    st.markdown(f"**Description:** {q['description']}")
    st.markdown("**Tables Involved:**")
    for table_name, table_data in q['table_info'].items():
        st.markdown(f"- **{table_name}**")
        if isinstance(table_data, dict):
            if 'columns' in table_data:
                st.write(f"  Columns: {', '.join(table_data['columns'])}")
            if 'sample' in table_data:
                st.markdown("  **Sample Data:**")
                # Parse and format sample data as table
                sample_text = table_data['sample']
                if ' ? ' in sample_text:
                    # Handle transformations like casting
                    parts = sample_text.split(' ? ')
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Input:**")
                        st.code(parts[0].strip())
                    with col2:
                        st.markdown("**Output:**")
                        st.code(parts[1].strip())
                elif ',' in sample_text and ':' in sample_text:
                    # Parse key-value pairs into table format
                    pairs = [p.strip() for p in sample_text.split(',')]
                    table_data_rows = []
                    for pair in pairs:
                        if ':' in pair:
                            key, value = pair.split(':', 1)
                            table_data_rows.append({"Column": key.strip(), "Value": value.strip()})
                    if table_data_rows:
                        st.dataframe(table_data_rows, width='stretch', hide_index=True)
                    else:
                        st.write(f"  {sample_text}")
                else:
                    st.write(f"  {sample_text}")
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
    
    if is_multiselect:
        st.info("⚠️ Select all that apply")
        for option in q["options"]:
            if st.checkbox(option, key=f"option_{st.session_state.current_q}_{option}"):
                # Extract letter (A, B, C, D)
                letter = option.split(".")[0].strip()
                selected_options.append(letter)
    else:
        selected_option = st.radio("Select the correct answer:", q["options"], key=f"option_{st.session_state.current_q}")
        if selected_option:
            letter = selected_option.split(".")[0].strip()
            selected_options = [letter]
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("Submit Answer", type="primary", key=f"submit_mcq_{st.session_state.current_q}"):
            if not selected_options:
                st.warning("Please select an answer before submitting.")
            else:
                # Check if selected answers match correct answers
                correct = set(selected_options) == set(q["correct_answers"])
                
                # Store answer
                st.session_state.answers.append({
                    "question_id": q["id"],
                    "question": q["question"],
                    "your_answer": ", ".join(selected_options),
                    "correct_answer": ", ".join(q["correct_answers"]),
                    "is_correct": correct,
                    "type": "mcq"
                })
                
                # Show feedback
                st.session_state.show_feedback = True
                st.session_state.feedback_correct = correct
                if correct:
                    st.session_state.feedback_message = "✅ Correct!"
                else:
                    st.session_state.feedback_message = "❌ Incorrect."
    
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
                st.session_state.current_q = len(st.session_state.shuffled_questions)
    
    # Show feedback for MCQ
    if st.session_state.show_feedback:
        if st.session_state.feedback_correct:
            st.success(st.session_state.feedback_message)
        else:
            st.error(st.session_state.feedback_message)
            with st.expander("View correct answer"):
                st.markdown(f"**Correct Answer(s):** {', '.join(q['correct_answers'])}")
                st.markdown("**Your Answer(s):** " + st.session_state.answers[-1]['your_answer'])
else:
    # SQL Question
    user_sql = st.text_area(
        "Enter your SQL query here:", 
        height=120,
        value=st.session_state.user_sql_input,
        key=f"sql_input_{st.session_state.current_q}"
    )
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("Submit Answer", type="primary", key=f"submit_sql_{st.session_state.current_q}"):
            if not user_sql.strip():
                st.warning("Please enter an answer before submitting.")
            else:
                # Normalize & compare
                normalized_candidate = normalize_sql(user_sql)
                normalized_solution = normalize_sql(q["solution"])
                
                correct = normalized_candidate == normalized_solution
                
                # Store answer
                st.session_state.answers.append({
                    "question_id": q["id"],
                    "question": q["question"],
                    "your_answer": user_sql,
                    "correct_answer": q["solution"],
                    "is_correct": correct,
                    "type": "sql"
                })
                
                # Show feedback
                st.session_state.show_feedback = True
                st.session_state.feedback_correct = correct
                if correct:
                    st.session_state.feedback_message = "✅ Correct!"
                else:
                    st.session_state.feedback_message = "❌ Incorrect."
    
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
                st.session_state.current_q = len(st.session_state.shuffled_questions)
    
    # Show feedback for SQL
    if st.session_state.show_feedback:
        if st.session_state.feedback_correct:
            st.success(st.session_state.feedback_message)
        else:
            st.error(st.session_state.feedback_message)
            with st.expander("View solution"):
                st.code(q["solution"], language="sql")
                st.markdown("**Explanation:**")
                st.write(f"Your answer: `{st.session_state.answers[-1]['your_answer']}`")

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
    if student_name and student_email:
        if not os.path.exists("submissions"):
            os.makedirs("submissions")
        
        # Get current submission datetime
        submission_datetime = datetime.now()
        
        # Create submission data
        submission_data = {
            "Name": student_name,
            "Email": student_email,
            "Submitted At": submission_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "Total Questions": total,
            "Correct Answers": correct_count,
            "Score (%)": round(score_percentage, 2)
        }
        
        # Add individual question results
        for i, ans in enumerate(st.session_state.answers):
            submission_data[f"Q{ans['question_id']}_Answer"] = ans['is_correct']
        
        # Save to submissions folder with timestamp
        submission_file = f"submissions/{student_email}_{submission_datetime.strftime('%Y%m%d_%H%M%S')}.csv"
        submission_df = pd.DataFrame([submission_data])
        submission_df.to_csv(submission_file, index=False)
        st.success(f"? Your results have been saved! (Submitted: {submission_datetime.strftime('%Y-%m-%d %H:%M:%S')})")
    
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
            <p style='color: #6B21A8; font-weight: 600; margin: 0;'>SQL Assessment Platform</p>
            <p style='color: #757575; font-size: 13px; margin: 0.5rem 0 0 0;'>SQL Mastery Program for Employee Training</p>
            <p style='color: #A78BFA; font-size: 11px; margin: 1rem 0 0 0;'>© 2026 SQL Assessment. All rights reserved.</p>
        </div>
    """, unsafe_allow_html=True)
