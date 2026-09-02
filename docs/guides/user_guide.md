[🇫🇷 Version française](user_guide.fr.md) | 🇬🇧 English version

---

# User Guide - GeoChallenge Tracker

## Overview

GeoChallenge Tracker is a full web application for geocaching enthusiasts. It lets you track your custom challenges, import your GPX finds, visualize your progress, and get completion statistics for your challenges.

## Authentication

### Sign up
1. Go to the sign-up page
2. Fill in the form with your information
3. Follow the password security requirements
4. Confirm your email address via the link sent to you

### Sign in
1. Go to the sign-in page
2. Enter your credentials
3. You are redirected to your dashboard

## Cache management

### Importing GPX files
1. Go to the "Caches" menu -> "Import GPX"
2. Select your GPX or ZIP file
3. Choose the import mode:
   - **All caches**: imports every cache from the file
   - **Found caches**: imports the caches and marks them as found for your account
4. The system automatically detects the format (c:geo, Pocket Query)

### Cache search
- Use the filtered search to find caches matching your criteria
- Available filters: type, size, difficulty, terrain, dates, attributes
- Geographic search within a rectangular or circular area

## Challenges

### Custom challenges
- Define your own challenges with custom criteria
- Track your progress in real time
- View target caches to reach your goals

### Classic challenges
#### D/T matrix
- Check your progress on the 9x9 difficulty/terrain matrix
- Identify missing combinations
- View target caches to complete the matrix

#### Calendar challenge
- Track your progress on the 365/366 day challenge
- Identify missing days
- Find target caches to complete the calendar

## Progress tracking

### Statistics
- Access your overall statistics in "My stats"
- View your progress over time
- Check completion projections

### History
- Track how your challenges evolve
- View historical progress snapshots
- Analyze your trends

## User profile

### Personal information
- Manage your profile information
- Set your location for personalized suggestions
- Customize your preferences

## Mapping

### Visualization
- View your found caches on the map
- Check the target caches for your challenges
- Use the drawing tools to plan your trips

### Choropleth map, found by zones

Accessible via the "Caches" menu -> "Found by zones".

This map colors regions and departments based on the number of caches you have found there.

**How to use it:**
1. The map opens on French **regions**, colored by density
2. **Hover** over a region to see its name and counter
3. **Click** a region to zoom in and display its **departments**
4. **Click** a department to open a popover with:
   - The total number of caches found in that department
   - The first 10 caches with their type, difficulty, and terrain
   - A "See all" link to access the full list
5. Use the **type filter** (at the top) to show only caches of a given type
6. Click **"Back to regions"** to go back up to the national level

### Choropleth map, types found by zones

Accessible via the "Caches" menu -> "Types found by zones".

This map colors zones based on the total number of caches found, but clicking shows the **breakdown by type** instead of the list of caches.

**How to use it:**
1. The map opens on French **regions**, colored by density
2. **Hover** over a zone to see its name and total counter
3. **Click** a zone to open a popover with:
   - The total number of caches found in that zone
   - A table listing the **13 cache types** with their respective counter
   - Types with no caches found are highlighted (pink background, red cross)
4. Switch between **Regions** and **Departments** via the buttons at the top, the popover closes automatically
5. Click **outside a zone** (on the map background) to close the popover

## Administration (for administrators)

### Maintenance tools
- Cleanup of orphaned data
- Database backup and restore
- Elevation data backfill

### Re-importing cache attributes
- **Access**: administrators only
- **Purpose**: re-import cache attributes from a GPX file
- **Use case**: correcting inconsistent cache attributes in the database
- **Procedure**: use the `/maintenance/upload-gpx` route to upload a GPX file
- **Impact**: updates the attributes of existing caches in the database
- **Caution**: this operation can significantly impact the database, use with care
