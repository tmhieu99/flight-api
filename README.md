# flight-api
A simple tool to get flight information by airport code using FastAPI

*** Potential improvements: ***

**1. Performance Enhancements:**

- Implement batch processing for multiple airport codes.
- Integrate Redis for efficient caching.
- Set up background tasks to prefetch data for popular airports.
- Store historical data in a database.

**2. User Interface Improvements:**

- Add loading indicators during API calls.
- Implement autocomplete for airport codes.
- Enable export functionality (CSV, PDF).
- Display historical trends over time.

**3. Error Handling & Reliability:**

- Introduce retry mechanisms with exponential backoff.
- Provide detailed error messages.
- Implement request validation middleware.
- Add request/response logging.

**4. New Features:**

- Support departure flights.
- Allow filtering by date ranges.
- Include flight details (airlines, flight numbers).
- Implement user preferences storage.

**5. Development Enhancements:**

- Set up a CI/CD pipeline.
- Document the API using OpenAPI/Swagger.
- Establish monitoring and alerting systems.
- Implement logging aggregation for multiple services.
- Collect metrics using Prometheus or Grafana.
