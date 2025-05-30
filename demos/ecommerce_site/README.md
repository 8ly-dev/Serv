# E-commerce Site Demo (MVP)

A simple e-commerce website built with Serv showcasing product catalogs, shopping cart functionality, and checkout processes with local storage.

## Features

- Product catalog with categories
- Shopping cart with session storage
- Simple checkout process
- Order management
- Product search and filtering
- Responsive design

## MVP TODO List

### Product Catalog
- [ ] Create product model with images and details
- [ ] Implement product categories and organization
- [ ] Add product listing pages with pagination
- [ ] Create individual product detail pages
- [ ] Add product image gallery
- [ ] Implement product search functionality

### Shopping Cart
- [ ] Session-based cart storage
- [ ] Add to cart functionality
- [ ] Cart page with quantity updates
- [ ] Remove items from cart
- [ ] Cart totals calculation
- [ ] Cart persistence across page refreshes

### Product Management
- [ ] JSON file storage for products
- [ ] Product filtering by category, price range
- [ ] Product sorting (price, name, popularity)
- [ ] Featured products section
- [ ] Related products suggestions
- [ ] Stock level tracking

### Checkout Process
- [ ] Customer information form
- [ ] Shipping address collection
- [ ] Order review and confirmation
- [ ] Simple order processing
- [ ] Order confirmation page
- [ ] Order history storage

### User Interface
- [ ] Homepage with featured products
- [ ] Product category navigation
- [ ] Search bar with auto-suggestions
- [ ] Shopping cart icon with item count
- [ ] Responsive product grid layout
- [ ] Mobile-friendly design

### Extensions Integration
- [ ] Create EcommerceExtension
- [ ] Add cart management middleware
- [ ] Create product catalog extension
- [ ] Add order processing extension

## Running the Demo

```bash
cd demos/ecommerce_site
pip install -r requirements.txt  # Pillow for image handling
serv launch
```

Visit http://localhost:8000 to browse the store!

## File Structure

```
demos/ecommerce_site/
├── README.md
├── requirements.txt              # Pillow for image processing
├── serv.config.yaml             # Basic config
├── data/
│   ├── products.json            # Product catalog
│   └── orders.json              # Order storage
├── static/
│   ├── images/
│   │   └── products/            # Product images
│   ├── store.js                 # Shopping cart functionality
│   └── style.css                # E-commerce styling
├── extensions/
│   ├── ecommerce_extension.py   # Main store functionality
│   ├── cart_extension.py        # Shopping cart logic
│   └── checkout_extension.py    # Checkout process
├── templates/
│   ├── store_home.html          # Homepage
│   ├── product_list.html        # Category/search results
│   ├── product_detail.html      # Individual product page
│   ├── cart.html                # Shopping cart
│   ├── checkout.html            # Checkout form
│   └── order_complete.html      # Order confirmation
└── models/
    ├── product.py               # Product data model
    └── order.py                 # Order data model
```

## MVP Scope

- **Local JSON storage** (no database required)
- **Session-based cart** (no user accounts)
- **Mock payment** (no payment processing)
- **Basic product catalog** (no complex inventory)
- **Minimal dependencies** (just Pillow for images)

## Product Data Model

```json
{
  "id": "prod_001",
  "name": "Wireless Headphones",
  "description": "High-quality wireless headphones...",
  "price": 99.99,
  "category": "electronics",
  "image": "/static/images/products/headphones.jpg",
  "stock": 15,
  "featured": true
}
```

## Store Features

### Product Browsing
- Homepage with featured products
- Category-based browsing (Electronics, Clothing, Books, etc.)
- Product search with live results
- Price range filtering
- Sort by price, name, or popularity

### Shopping Experience
- Add products to cart from any page
- View cart with running total
- Update quantities in cart
- Remove items from cart
- Persistent cart across browser sessions

### Checkout Process
1. **Cart Review**: View items and totals
2. **Customer Info**: Name, email, phone
3. **Shipping Address**: Address form
4. **Order Review**: Final confirmation
5. **Order Complete**: Success page with order number

## Sample Products

The demo includes products across categories:
- **Electronics**: Phones, laptops, headphones, cameras
- **Clothing**: Shirts, jeans, shoes, accessories
- **Books**: Fiction, non-fiction, textbooks
- **Home**: Furniture, kitchen items, decor

## Store Pages

- `/` - Homepage with featured products
- `/category/{name}` - Category product listings
- `/product/{id}` - Individual product details
- `/search?q={term}` - Search results
- `/cart` - Shopping cart management
- `/checkout` - Checkout process
- `/orders` - Order history (session-based)

This MVP demonstrates Serv's capabilities for building e-commerce websites! 