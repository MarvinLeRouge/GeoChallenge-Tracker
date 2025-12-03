# 🧭 GeoChallenge Tracker - Technologies

## 🧱 Backend Technologies

### Core Framework
- **FastAPI** - Modern, fast (high-performance) web framework for building APIs with Python 3.7+ based on standard Python type hints

### Database
- **MongoDB** - NoSQL database for storing geocache data, user information, and challenges
- **Motor** - Asynchronous Python driver for MongoDB

### Authentication & Security
- **JWT (JSON Web Tokens)** - For secure user authentication and authorization
- **Python-JOSE** - For JWT token encoding/decoding
- **PassLib** - For password hashing and verification

### Dependencies & Utilities
- **Pydantic** - Data validation and settings management using Python type annotations
- **Python-Multipart** - For handling multipart form data (file uploads)
- **python-dotenv** - For managing environment variables
- **Bcrypt** - For password hashing
- **Pillow** - Python Imaging Library

## 🖥️ Frontend Technologies

### Core Framework
- **Vue.js 3** - Progressive JavaScript framework for building user interfaces
- **TypeScript** - Typed superset of JavaScript that compiles to plain JavaScript
- **Vue Router** - Official router for Vue.js
- **Pinia** - Intuitive store for Vue.js

### UI & Styling
- **Tailwind CSS** - Utility-first CSS framework for rapid UI development
- **Flowbite** - Open-source library of interactive UI components
- **Flowbite Vue** - Vue.js components based on Flowbite
- **Heroicons Vue** - Beautiful hand-crafted SVG icons
- **Lucide Vue** - Beautiful & consistent icon toolkit as Vue components

### Maps & Visualization
- **Leaflet** - Open-source JavaScript library for mobile-friendly interactive maps
- **Leaflet Draw** - Interactive drawing tools for Leaflet maps
- **Leaflet Markercluster** - Marker clustering library for Leaflet

### Development Tools
- **Vite** - Next-generation frontend tooling with fast hot module replacement
- **ESLint** - JavaScript/TypeScript linter for identifying problematic patterns
- **Vue TSC** - Type checking for Vue projects
- **PostCSS** - CSS post-processor

### Testing
- **Vitest** - Blazing fast test runner for Vite and Vue projects
- **Playwright** - End-to-end testing framework
- **JSDOM** - JavaScript implementation of web standards

## 🐳 DevOps & Deployment

### Containerization
- **Docker** - Platform for developing, shipping, and running applications in containers
- **Docker Compose** - Tool for defining and running multi-container Docker applications

### Infrastructure
- **Nginx** - Web server used as reverse proxy for the frontend
- **MongoDB Atlas** - Cloud-hosted MongoDB database service (externally hosted)

## 🛠️ Development Tools & Practices

### Code Quality
- **TypeScript** - Static typing for JavaScript
- **ESLint** - Code linting and quality assurance
- **Prettier** - Code formatter
- **TDD (Test Driven Development)** - Backend testing approach
- **E2E Testing** - Frontend testing approach

### Architecture
- **Service Layer Pattern** - Separation of business logic in backend
- **Composables** - Reusable business logic in frontend
- **Component-based architecture** - In Vue.js frontend
- **RESTful API design** - For backend endpoints
- **JWT Authentication** - Secure token-based authentication