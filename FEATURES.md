# 🧭 GeoChallenge Tracker - Features & Functionality

## 🎯 Overview
GeoChallenge Tracker is a comprehensive tool designed for geocachers to track and manage their geocaching challenges. It allows users to define and follow their personalized challenges, import their finds from GPX files, visualize their progress on a map, and get completion projections through statistics.

## 🔐 Authentication & User Management

### User Registration & Authentication
- **User Registration** - Create an account with username, email, and password
- **Secure Login** - Authenticate users with email/username and password
- **JWT-based Session Management** - Secure token-based authentication
- **Email Verification** - Confirm user email addresses with verification codes
- **Password Strength Validation** - Enforce strong password requirements
- **Account Recovery** - Resend verification emails when needed

### User Profile Management
- **Location Storage** - Save and update user's current location (coordinates or text format)
- **Profile Retrieval** - Get current user profile information
- **Coordinate Parsing** - Support for multiple coordinate formats (degrees/minutes)

## 🗺️ Cache Management

### Data Import & Processing
- **GPX File Upload** - Import geocaches from GPX files (cgeo, pocket_query formats)
- **ZIP Support** - Import from ZIP files containing GPX data
- **Cache Discovery Mode** - Import caches for future discovery
- **Find Marking Mode** - Mark caches as found by the user
- **Automatic Challenge Creation** - Generate challenges based on imported caches

### Cache Search & Filtering
- **Advanced Filtering** - Filter caches by type, size, difficulty, terrain, attributes
- **Text Search** - Full-text search across cache descriptions
- **Date Filtering** - Filter by placement dates
- **Attribute-based Filtering** - Filter by positive and negative attributes
- **Geographic Search** - Search within bounding boxes and radius
- **Map Integration** - Visualize caches on interactive maps

## 🎮 Challenge System

### Challenge Tracking
- **User Challenge Synchronization** - Sync user's challenges with available challenges
- **Challenge Status Management** - Track pending, accepted, dismissed, completed status
- **Bulk Challenge Updates** - Batch update multiple challenges at once
- **Detailed Challenge View** - Access full details of individual challenges

### Challenge Types
- **Matrix Challenges** - Track Difficulty/Terrain combinations (D/T matrix)
- **Calendar Challenges** - Track finding at least one cache each day of the year
- **Custom Challenges** - Define personalized challenges with specific criteria
- **Basic Challenges** - Predefined common challenge types

## 📊 Progress Tracking

### Progress Evaluation
- **Real-time Progress Updates** - Evaluate and store progress snapshots
- **Historical Tracking** - Keep history of progress over time
- **Progress Visualization** - View progress trends and statistics
- **Automated Progress Calculation** - Calculate initial progress for new challenges

### Matrix & Calendar Verification
- **D/T Matrix Verification** - Check completion of all Difficulty/Terrain combinations
- **Calendar Verification** - Check completion of all days in a year
- **Filtering Support** - Filter by cache type and size for matrix/calendar challenges
- **Completion Statistics** - Visualize completion rates and missing items

## 🎯 Target Identification

### Smart Targeting
- **Target Evaluation** - Identify caches that satisfy challenge requirements
- **Geographic Targeting** - Find nearby targets based on user location
- **Target Scoring** - Score targets based on relevance to challenges
- **Location-based Filtering** - Filter targets by proximity to user location

### Target Management
- **Target Listing** - View all identified targets for any challenge
- **Nearby Targets** - Find targets close to current location
- **Target Cleanup** - Remove all targets for a specific challenge
- **Batch Target Operations** - Perform operations on multiple targets

## 📋 Task Management

### Challenge Tasks
- **Task Definition** - Define specific tasks that make up a challenge
- **Task Ordering** - Specify the order in which tasks should be completed
- **Task Validation** - Validate task definitions without persisting
- **Task Replacement** - Update all tasks for a challenge at once

## 📊 Statistics & Analytics

### Completion Tracking
- **Matrix Visualization** - Interactive grid showing D/T completion status
- **Calendar View** - Visual calendar showing daily completion status
- **Statistics Dashboard** - View completion rates and progress metrics
- **Filtering Options** - Filter statistics by cache type and size

### Data Visualization
- **Interactive Grids** - Visualize matrix and calendar challenges
- **Real-time Updates** - See statistics update as filters change
- **Completion Metrics** - Track overall and specific challenge completion rates
- **Visual Indicators** - Color-coded status indicators for completed/incomplete items

## 🗃️ Data Management

### Maintenance Operations
- **Database Cleanup** - Identify and remove orphaned records
- **Backup Creation** - Create full database backups
- **Backup Management** - List and download existing backups
- **Data Restoration** - Restore from backup files
- **Orphan Detection** - Find references to non-existent records

### Data Enrichment
- **Elevation Data** - Backfill missing elevation data for caches
- **Geographic Data** - Integrate with external geolocation services
- **Cache Attributes** - Store and manage cache attributes
- **Nested Data Handling** - Manage complex nested data structures

## 🌐 Frontend Features

### User Interface
- **Responsive Design** - Works on desktop and mobile devices
- **Interactive Maps** - Visualize geocaches and challenges on maps
- **Modern UI Components** - Clean, intuitive interface with flowbite components
- **Dark Mode Support** - Toggle between light and dark themes

### User Experience
- **Real-time Filtering** - Instant feedback when applying filters
- **Progress Indicators** - Visual feedback during operations
- **Error Handling** - Clear error messages and recovery options
- **Form Validation** - Client-side validation for form inputs

## 🔧 Administrative Features

### Admin Interface
- **Admin Authentication** - Special permissions for administrative tasks
- **Database Management** - Tools for database maintenance and monitoring
- **User Management** - Access to user data and account management
- **System Configuration** - Adjust system-wide settings and parameters

### System Tools
- **Elevation Backfill** - Admin tool to add elevation data to caches
- **Challenge Refresh** - Regenerate challenges from existing data
- **System Monitoring** - Track system usage and performance
- **Data Import Tools** - Specialized tools for data management