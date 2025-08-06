import streamlit as st
import pandas as pd
import re
import io
from typing import Tuple, Optional

def parse_course_semester_grade(column_name: str) -> Optional[Tuple[str, str, str, str]]:
    """
    Parse a column name in format 'Course-Semester-Year-Grade' or similar variations.
    
    Args:
        column_name: String like 'MATH101-Fall2024-A' or 'BIO202-Spring2025-B+'
    
    Returns:
        Tuple of (course, semester, year, grade) or None if parsing fails
    """
    # Pattern to match course-semester-year-grade format
    # Supports various grade formats including A+, B-, etc.
    pattern = r'^([A-Z]+\d+)-([A-Za-z]+)(\d{4})-([A-F][+-]?|[A-F]|[A-Z][+-]?)$'
    
    match = re.match(pattern, column_name.strip())
    if match:
        course, semester, year, grade = match.groups()
        return course, semester, year, grade
    
    # Alternative pattern for different formats
    pattern2 = r'^([A-Z]+\d+)[-_]([A-Za-z]+)[-_](\d{4})[-_]([A-F][+-]?|[A-F]|[A-Z][+-]?)$'
    match2 = re.match(pattern2, column_name.strip())
    if match2:
        course, semester, year, grade = match2.groups()
        return course, semester, year, grade
    
    return None

def identify_grade_columns(df: pd.DataFrame) -> list:
    """
    Identify columns that contain grade data based on naming patterns.
    
    Args:
        df: Input DataFrame
    
    Returns:
        List of column names that appear to contain grade data
    """
    grade_columns = []
    
    for col in df.columns:
        if parse_course_semester_grade(str(col)) is not None:
            grade_columns.append(col)
    
    return grade_columns

def transform_grades_to_tidy(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform wide-format grade data to tidy format.
    
    Args:
        df: Input DataFrame with wide-format grade data
    
    Returns:
        Transformed DataFrame in tidy format
    """
    # Make a copy to avoid modifying original
    df_copy = df.copy()
    
    # Drop columns that are entirely empty
    df_copy = df_copy.dropna(axis=1, how='all')
    
    # Identify demographic/ID columns (non-grade columns)
    grade_columns = identify_grade_columns(df_copy)
    id_columns = [col for col in df_copy.columns if col not in grade_columns]
    
    if not grade_columns:
        st.warning("No grade columns detected. Please ensure your column names follow the format: Course-Semester-Year-Grade (e.g., MATH101-Fall2024-A)")
        return pd.DataFrame()
    
    # Melt the DataFrame to convert from wide to long format
    melted_df = pd.melt(
        df_copy,
        id_vars=id_columns,
        value_vars=grade_columns,
        var_name='Course_Semester_Grade',
        value_name='Grade'
    )
    
    # Filter out missing values
    melted_df = melted_df.dropna(subset=['Grade'])
    
    # Remove rows where Grade is empty string or whitespace
    melted_df = melted_df[melted_df['Grade'].astype(str).str.strip() != '']
    
    # Parse the Course_Semester_Grade column
    parsed_data = []
    
    for _, row in melted_df.iterrows():
        parsed = parse_course_semester_grade(row['Course_Semester_Grade'])
        if parsed:
            course, semester, year, grade = parsed
            
            # Create new row with parsed data
            new_row = {}
            
            # Add ID columns
            for id_col in id_columns:
                new_row[id_col] = row[id_col]
            
            # Add parsed course information
            new_row['Course'] = course
            new_row['Semester'] = semester
            new_row['Year'] = int(year)
            new_row['Grade'] = grade
            
            parsed_data.append(new_row)
    
    # Create final DataFrame
    if parsed_data:
        tidy_df = pd.DataFrame(parsed_data)
        
        # Reorder columns for better readability
        base_columns = [col for col in id_columns]
        course_columns = ['Course', 'Semester', 'Year', 'Grade']
        final_columns = base_columns + course_columns
        
        tidy_df = tidy_df[final_columns]
        
        return tidy_df
    else:
        return pd.DataFrame()

def main():
    st.title("📊 Student Grade Data Transformer")
    st.markdown("Transform wide-format student grade Excel files into tidy, normalized data for academic analysis")
    
    # File upload section
    st.header("1. Upload Excel File")
    uploaded_file = st.file_uploader(
        "Choose an Excel file",
        type=['xlsx', 'xls'],
        help="Upload an Excel file containing student grade data in wide format"
    )
    
    if uploaded_file is not None:
        try:
            # Read the Excel file
            df = pd.read_excel(uploaded_file)
            
            st.success(f"✅ File uploaded successfully! Shape: {df.shape[0]} rows × {df.shape[1]} columns")
            
            # Show original data preview
            st.header("2. Original Data Preview")
            st.dataframe(df.head(10), use_container_width=True)
            
            # Analyze the data
            st.header("3. Data Analysis")
            
            # Check for empty columns
            empty_cols = df.columns[df.isnull().all()].tolist()
            if empty_cols:
                st.info(f"Found {len(empty_cols)} empty columns that will be removed: {', '.join(empty_cols)}")
            
            # Identify grade columns
            grade_columns = identify_grade_columns(df)
            if grade_columns:
                st.info(f"Detected {len(grade_columns)} grade columns: {', '.join(grade_columns[:5])}{'...' if len(grade_columns) > 5 else ''}")
            else:
                st.error("❌ No grade columns detected. Please ensure your column names follow the format: Course-Semester-Year-Grade (e.g., MATH101-Fall2024-A)")
                return
            
            # Transform the data
            st.header("4. Data Transformation")
            
            with st.spinner("Transforming data..."):
                tidy_df = transform_grades_to_tidy(df)
            
            if not tidy_df.empty:
                st.success(f"✅ Data transformed successfully! New shape: {tidy_df.shape[0]} rows × {tidy_df.shape[1]} columns")
                
                # Show transformation summary
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Original Rows", df.shape[0])
                with col2:
                    st.metric("Transformed Rows", tidy_df.shape[0])
                with col3:
                    st.metric("Unique Students", tidy_df.iloc[:, 0].nunique() if len(tidy_df.columns) > 0 else 0)
                
                # Show transformed data preview
                st.header("5. Transformed Data Preview")
                st.dataframe(tidy_df.head(20), use_container_width=True)
                
                # Show summary statistics
                st.header("6. Summary Statistics")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Courses")
                    if 'Course' in tidy_df.columns:
                        course_counts = tidy_df['Course'].value_counts()
                        st.dataframe(course_counts.head(10), use_container_width=True)
                
                with col2:
                    st.subheader("Grade Distribution")
                    if 'Grade' in tidy_df.columns:
                        grade_counts = tidy_df['Grade'].value_counts()
                        st.dataframe(grade_counts, use_container_width=True)
                
                # Download section
                st.header("7. Download Cleaned Data")
                
                # Create Excel file in memory
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    tidy_df.to_excel(writer, sheet_name='Cleaned_Data', index=False)
                
                output.seek(0)
                
                st.download_button(
                    label="📥 Download Cleaned Excel File",
                    data=output.getvalue(),
                    file_name="cleaned_student_data.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
            else:
                st.error("❌ No valid data could be extracted. Please check your file format and column naming conventions.")
                
        except Exception as e:
            st.error(f"❌ Error processing file: {str(e)}")
            st.info("Please ensure your file is a valid Excel file with the correct format.")
    
    # Instructions section
    with st.expander("📋 Instructions & Format Requirements"):
        st.markdown("""
        ### Expected File Format
        
        Your Excel file should have:
        
        1. **Student Information Columns**: ID, NAME, MAJOR, etc.
        2. **Grade Columns**: Named in format `Course-Semester-Year-Grade`
           - Example: `MATH101-Fall2024-A`, `BIO202-Spring2025-B+`
           - Course: Letters followed by numbers (e.g., MATH101, BIO202)
           - Semester: Fall, Spring, Summer, Winter
           - Year: 4-digit year (e.g., 2024, 2025)
           - Grade: Standard letter grades (A, B, C, D, F) with optional +/- modifiers
        
        ### What This Tool Does
        
        1. **Loads** your Excel file into a DataFrame
        2. **Drops** any columns that are entirely empty
        3. **Melts** the data from wide to long format
        4. **Filters** out missing values
        5. **Splits** combined Course_Semester_Grade strings into separate fields:
           - Course (e.g., "MATH101")
           - Semester (e.g., "Fall")
           - Year (e.g., "2024")
           - Grade (e.g., "A")
        6. **Exports** the result as a new Excel file
        
        ### Output Format
        
        The cleaned data will have columns like:
        ```
        ID | NAME | MAJOR | Course | Semester | Year | Grade
        ```
        """)

if __name__ == "__main__":
    main()
