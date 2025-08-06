# Overview

This is a Streamlit-based academic grade analysis application that processes student grade data. The application focuses on parsing and analyzing grade information from structured datasets, with specialized functionality for interpreting course-semester-year-grade naming conventions. It's designed to handle academic data where grades are stored in columns with specific naming patterns like 'MATH101-Fall2024-A' or 'BIO202-Spring2025-B+'.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
- **Streamlit Framework**: Uses Streamlit for the web interface, providing an interactive dashboard for grade data analysis
- **Single-page Application**: Built as a simple SPA with Streamlit's component-based structure

## Data Processing Architecture
- **Pandas-based Data Handling**: Core data manipulation using pandas DataFrames for efficient tabular data processing
- **Pattern Recognition System**: Custom regex-based parsing system to extract structured information from column names
- **Modular Parsing Functions**: Separated parsing logic into reusable functions for course, semester, year, and grade extraction

## Data Structure Design
- **Column Name Convention**: Expects grade data in 'Course-Semester-Year-Grade' format (e.g., 'MATH101-Fall2024-A')
- **Flexible Pattern Matching**: Supports multiple delimiter variations (hyphens and underscores)
- **Grade Format Support**: Handles various grade formats including letter grades with plus/minus modifiers (A+, B-, etc.)

## Error Handling and Validation
- **Optional Return Types**: Uses Python's typing system with Optional types for robust error handling
- **Pattern Fallback**: Implements multiple regex patterns to catch different naming convention variations
- **Graceful Failures**: Returns None for unparseable column names rather than throwing exceptions

# External Dependencies

## Core Libraries
- **Streamlit**: Web application framework for creating the interactive interface
- **Pandas**: Data manipulation and analysis library for handling tabular data
- **Python Standard Library**:
  - `re`: Regular expression module for pattern matching and parsing
  - `io`: Input/output utilities for data handling
  - `typing`: Type hints for better code documentation and IDE support

## Data Sources
- **File Upload Integration**: Designed to work with uploaded CSV/Excel files containing student grade data
- **Structured Data Expectations**: Requires input data with specific column naming conventions for grade information