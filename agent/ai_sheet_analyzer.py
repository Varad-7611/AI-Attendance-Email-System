import json
import os
from groq import Groq
from agent.logger import setup_logger

logger = setup_logger("AISheetAnalyzer")

class AISheetAnalyzer:
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError("Groq API Key is not set.")
        self.client = Groq(api_key=api_key)
        self.model = model

    def analyze_sheet_structure(self, sample_rows: list) -> dict:
        """
        Uses Groq to analyze the structure of a spreadsheet based on its first few rows.
        Returns a mapping dict.
        """
        logger.info("Analyzing sheet structure via AI Agent...")
        
        if not sample_rows:
            logger.warning("No sample rows provided for AI analysis.")
            return {}

        # Serialize the sample rows for the LLM
        serialized_rows = []
        for idx, row in enumerate(sample_rows[:20]): # Limit to first 20 rows
            # Clean cells to avoid excess whitespace
            cleaned_row = [str(cell).strip() if cell is not None else "" for cell in row]
            # Skip completely empty rows from the serialization to save context space
            if any(cleaned_row):
                serialized_rows.append(f"Row {idx}: {cleaned_row}")
        
        rows_str = "\n".join(serialized_rows)
        
        system_prompt = (
            "You are an expert data analysis agent that analyzes student attendance sheet schemas.\n"
            "Given a representation of the first few rows of an attendance spreadsheet, "
            "you must determine how to programmatigally parse student attendance records.\n"
            "Analyze the headers, columns, and sample entries to detect:\n"
            "1. Which row contains headers (e.g. including labels like 'Name', 'Roll', 'Email', etc.).\n"
            "2. Which row the student records start (data start row).\n"
            "3. The column indexes (0-based) for Roll Number, Student Name, and Email.\n"
            "4. The values used to represent present (e.g., 'P', '1', 'TRUE', 'Present') and absent (e.g., 'A', '0', 'FALSE', 'Absent').\n"
            "5. A list of columns that correspond to specific class lectures/sessions/timings/subjects. Extract their 0-based column index, subject name, and lecture timing if mentioned.\n\n"
            "Respond ONLY with a valid JSON object matching the following structure:\n"
            "{\n"
            "  \"header_row_index\": int,\n"
            "  \"data_start_row_index\": int,\n"
            "  \"roll_no_col_index\": int,\n"
            "  \"name_col_index\": int,\n"
            "  \"email_col_index\": int,\n"
            "  \"present_value\": \"string\",\n"
            "  \"absent_value\": \"string\",\n"
            "  \"lectures\": [\n"
            "    { \"col_index\": int, \"subject\": \"string\", \"timing\": \"string\" }\n"
            "  ]\n"
            "}"
        )
        
        user_prompt = f"Analyze the following sample rows from the spreadsheet:\n\n{rows_str}"
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.model,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            response_text = chat_completion.choices[0].message.content.strip()
            mapping = json.loads(response_text)
            logger.info(f"AI sheet analysis result: {mapping}")
            return mapping
        except Exception as e:
            logger.error(f"Error during AI sheet structure analysis: {e}")
            return {}
