# Overview

This is a Streamlit-based academic grade analysis application that processes student grade data for the PU PBHL Department. The application transforms wide-format student grade Excel files into tidy, normalized data for academic analysis. It supports two data formats: column-based naming conventions (Course-Semester-Year-Grade) and cell-value formats (Course/Semester-Year/Grade). Successfully tested with PU PBHL data containing formats like 'SPTH201/FALL-2016/F'.

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
- **Dual Format Support**: 
  - Format 1: Column names in 'Course-Semester-Year-Grade' format (e.g., 'MATH101-Fall2024-A')
  - Format 2: Course columns (COURSE_1, COURSE_2, etc.) with cell values in 'Course/Semester-Year/Grade' format (e.g., 'SPTH201/FALL-2016/F')
- **Flexible Pattern Matching**: Supports multiple delimiter variations (hyphens, underscores, forward slashes)
- **Grade Format Support**: Handles various grade formats including letter grades with plus/minus modifiers (A+, B-, etc.), plus special grades (P, R, INCOMPLETE)

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