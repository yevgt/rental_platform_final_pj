# Rental Platform Backend

A comprehensive Django REST API backend for a rental housing platform, 
providing complete functionality for property management, booking system, reviews, and analytics.

## Features

### 🏠 Property Management
- Complete property listings with detailed information
- Image upload and management
- Property search and filtering by multiple criteria
- Property status management 

### 👥 User Management
- Custom user model with role-based access (tenant/landlord)
- JWT authentication and authorization
- User profiles with extended information
- Email-based registration and login

### 📅 Booking System
- Date-based booking with conflict detection
- Status tracking (pending, confirmed, cancelled, completed)
- Landlord confirmation workflow

### ⭐ Review & Rating System
- Property reviews with detailed ratings
- Landlord response system
- Verified reviews for completed bookings

### 📊 Analytics & Insights
- Property view tracking
- Search query analytics

## Technology Stack

- **Backend Framework:** Django 5.2+ with Django REST Framework
- **Authentication:** JWT (djangorestframework-simplejwt)
- **Database:** SQLite (development) / MySQL (production)
- **Image Handling:** Pillow for image processing
- **API Documentation:** Django REST Framework docs with CoreAPI
- **Filtering:** django-filter for advanced query filtering
- **Docker:**  create docker-image for project containerization

## API Endpoints

### Authentication
- `POST /api/accounts/register/` - User registration
- `POST /api/auth-login/` - User login
- `POST /api/auth-logout/` - User logout
- `GET /api/accounts/me/` - Get user profile
- `PUT /api/auth/accounts/me-update/` - Update user profile
- `POST /api/accounts/change-password/` - Change password
- `DELETE /api/accounts/change-password/` - Delete user profile

### Properties
- `GET /api/properties/` - List properties
- `POST /api/properties/create/` - Create property (landlords only)
- `GET /api/properties/{id}/` - Property details
- `PUT /api/properties/{id}/` - Update property (owner only)
- `DELETE /api/properties/{id}/` - Delete property (owner only)
- `GET /api/properties/public/` - Public properties

### Bookings
- `GET /api/bookings/create/` - List bookings (rentner only)
- `POST /api/bookings/create/` - Create booking
- `POST /api/bookings/{id}/confirm/cancel` - Cancel booking (rentner)
- `GET /api/bookings/{id}/` - Booking details
- `PUT /api/bookings/{id}/` - Update booking status
- `POST /api/bookings/{id}/confirm/` - Confirm booking (landlord)
- `POST /api/bookings/{id}/reject/` - Cancel booking (landlord)
- `GET /api/bookings/{id}/messages/` - massage rentner to landlord
- `GET /api/bookings/available_properties/` - Landlord's property bookings

### Reviews
- `POST /api/reviews/` - Create review
- `GET /api/reviews/{id}/` - Review details
- `PUT /api/reviews/{id}/` - Update review (author only)

### Analytics
- `GET /api/analytics/top-properties/` - Top properties
- `GET /api/analytics/popular-searches/` - Popular searches

## Quick Start

### Prerequisites
- Python 3.8+
- pip (Python package manager)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd rental_platform_backend
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment setup**
   ```bash
   cp .env.example .env
   ```

4. **Run migrations**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

5. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

6. **Start development server**
   ```bash
   python manage.py runserver
   ```

The API will be available at `http://localhost:8000/`

### API Documentation
Visit `http://localhost:8000/api/docs/` for interactive API documentation.

### Admin Panel
Access the Django admin panel at `http://localhost:8000/admin/`

## Configuration

### Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# Django settings
SECRET_KEY=django-insecure-..............................
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (for production use MySQL)
# DB switch: 0 - SQLite (default), 1 - MySQL

DATABASE_URL=sqlite:///db.sqlite3

# MySQL connection (используется, если MYSQL=1)
# MYSQL_NAME=name db
# MYSQL_USER=name
# MYSQL_PASSWORD=password
# MYSQL_HOST=name host
# MYSQL_PORT=3306

# JWT Settings
JWT_SECRET_KEY=your-jwt-secret-key
```
## Project Structure

```
rental-housing-backend/
├── accounts/              # User management app
├── analytics/             # Analytics and reporting
├── bookings/              # Booking system
├── properties/            # Property management
├── rental_platform/       # Main project settings
├── reviews/               # Review and rating system
├── docker-compose.yml     # Сonfiguration file for Docker container
├── Dockerfile             # instructions for building a Docker image
├── manage.py              # Django management script
├── pytest.ini             # Сonfiguration file for tests
├── README.md              # This file
└── requirements.txt       # Python dependencies
```

## Data Models

### User (Extended Django User)
- Role-based access (rentner/landlord)
- Profile information with photo upload
- Email verification system

### Property
- Comprehensive property information
- Multiple image support
- Availability tracking

### Booking
- Date-based reservation system
- Status workflow management
- Conflict detection

### Review
- Multi-dimensional rating system
- Verified review requirements
- Landlord response capability

### Analytics Models
- Search query tracking
- Property view analytics

## API Authentication

This API uses JWT (JSON Web Tokens) for authentication. 
Include the access token in the Authorization header:

```
Authorization: Bearer <access_token>
```

### Token Endpoints
- Get tokens: `POST /api/token/`
- Refresh token: `POST /api/token/refresh/`


## Permissions

- **Public:** Property listings, property details, reviews (read-only)
- **Authenticated:** Profile management, booking creation, review creation
- **Rentner:** Booking management
- **Landlords:** Property management, booking confirmations
- **Property Owners:** Update/delete their properties, respond to reviews
- **Admin:** Full access, analytics trends

## Testing

Run the test suite:
```bash
python manage.py test
```

## Production Deployment

### Settings Checklist
- [ ] Set `DEBUG=False`
- [ ] Configure proper `SECRET_KEY`
- [ ] Set up PostgreSQL database
- [ ] Configure static file serving
- [ ] Set up media file storage
- [ ] Configure CORS for your frontend domain
- [ ] Set proper `ALLOWED_HOSTS`

### Recommended Production Stack
- **Web Server:** Nginx
- **WSGI Server:** Gunicorn
- **Database:** MySQL
- **Static Files:** WhiteNoise or separate CDN
- **Media Storage:** AWS S3 or similar

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For questions or support, please open an issue in the repository.