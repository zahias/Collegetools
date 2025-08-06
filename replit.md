# Overview

This is a comprehensive Streamlit-based academic data processing toolkit for the PU PBHL Department. The application combines two essential tools in a tabbed interface: a Grade Data Transformer for processing student grade records, and an Internship Data Consolidator for managing student internship completion data. Both tools support the specific data formats used by the department and provide Excel export functionality for downstream analysis.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
- **Streamlit Framework**: Uses Streamlit for the web interface with a tabbed multi-tool dashboard
- **Multi-Tool Application**: Built with tab-based navigation separating grade analysis and internship consolidation
- **Wide Layout**: Configured for optimal display of data tables and processing results

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
- **OpenPyXL**: Excel file reading and writing for direct workbook manipulation
- **Python Standard Library**:
  - `re`: Regular expression module for pattern matching and parsing
  - `io`: Input/output utilities for data handling
  - `zipfile`: Archive processing for batch file operations
  - `os`: Operating system interface for file path operations
  - `tempfile`: Secure temporary file creation and management
  - `typing`: Type hints for better code documentation and IDE support

## Data Sources
- **File Upload Integration**: Designed to work with uploaded CSV/Excel files containing student grade data
- **Structured Data Expectations**: Requires input data with specific column naming conventions for grade information