from config.constants import Settings
from agent.logger import setup_logger

logger = setup_logger("AttendanceProcessor")

class AttendanceProcessor:
    def __init__(self, rows: list, ai_mapping: dict = None):
        self.rows = rows
        self.ai_mapping = ai_mapping
        self.timings = []
        self.subjects = []
        if not self.ai_mapping:
            self._parse_headers()
        else:
            self._parse_headers_from_ai()

    def _parse_headers(self):
        """Extract lectures timings and subjects from the headers dynamically (standard method)."""
        header_row_idx = Settings.SUBJECT_ROW_INDEX
        for idx, row in enumerate(self.rows):
            if any("Email" in str(cell) or "Roll No" in str(cell) for cell in row):
                header_row_idx = idx
                break
                
        if len(self.rows) <= header_row_idx:
            return
            
        header_subjects = self.rows[header_row_idx]
        if header_row_idx > 0 and self.rows[header_row_idx - 1]:
            header_timings = self.rows[header_row_idx - 1]
        else:
            header_timings = header_subjects
            
        self.data_start_idx = header_row_idx + 1
        max_len = max(len(header_timings), len(header_subjects))
        
        for col_index in range(Settings.LECTURE_START_COL, max_len):
            timing = header_timings[col_index] if col_index < len(header_timings) else "Unknown Time"
            subject = header_subjects[col_index] if col_index < len(header_subjects) else "Unknown Subject"
            
            if not timing.strip() and not subject.strip():
                break
                
            self.timings.append(timing.strip())
            self.subjects.append(subject.strip())

    def _parse_headers_from_ai(self):
        """Map variables from AI schema."""
        self.data_start_idx = self.ai_mapping.get('data_start_row_index', 2)
        lectures_map = self.ai_mapping.get('lectures', [])
        for lect in lectures_map:
            self.timings.append(lect.get('timing', 'Unknown Time'))
            self.subjects.append(lect.get('subject', 'Unknown Subject'))

    def get_absent_students(self) -> dict:
        """
        Original method compatibility for main.py.
        Returns format: {email: {name, roll_no, absent_lectures}}
        """
        students = self.get_all_students_details()
        absent_data = {}
        for s in students:
            if s['status'] == 'Absent' and s['email']:
                absent_data[s['email']] = {
                    "name": s['name'],
                    "roll_no": s['roll_no'],
                    "absent_lectures": s['absent_lectures']
                }
        return absent_data

    def get_all_students_details(self) -> list:
        """
        Analyzes all rows and maps student name, roll no, email, status (Absent vs Present),
        and list of present/absent lectures.
        """
        student_details = []
        
        # Extract indices/parameters
        if self.ai_mapping:
            data_start = self.ai_mapping.get('data_start_row_index', 2)
            roll_col = self.ai_mapping.get('roll_no_col_index', 0)
            name_col = self.ai_mapping.get('name_col_index', 1)
            email_col = self.ai_mapping.get('email_col_index', 2)
            absent_val = str(self.ai_mapping.get('absent_value', 'A')).strip().upper()
            present_val = str(self.ai_mapping.get('present_value', 'P')).strip().upper()
            lectures_def = self.ai_mapping.get('lectures', [])
        else:
            data_start = getattr(self, 'data_start_idx', Settings.DATA_START_ROW_INDEX)
            roll_col = Settings.ROLL_NO_COL
            name_col = Settings.NAME_COL
            email_col = Settings.EMAIL_COL
            absent_val = Settings.ABSENT_VALUE.upper()
            present_val = Settings.PRESENT_VALUE.upper()
            # Construct compatible lectures details
            lectures_def = []
            for i in range(len(self.timings)):
                lectures_def.append({
                    "col_index": Settings.LECTURE_START_COL + i,
                    "subject": self.subjects[i],
                    "timing": self.timings[i]
                })

        if len(self.rows) <= data_start:
            return student_details

        logger.info(f"Scanning attendance using data start index {data_start}...")

        for row_index in range(data_start, len(self.rows)):
            row = self.rows[row_index]
            if not row:
                continue
                
            # Grab student identification details safely
            roll_no = str(row[roll_col]).strip() if roll_col < len(row) else ""
            name = str(row[name_col]).strip() if name_col < len(row) else ""
            email = str(row[email_col]).strip() if email_col < len(row) else ""

            # If all identifying fields are blank, it could be a divider/empty row
            if not roll_no and not name and not email:
                continue

            absent_lectures = []
            present_lectures = []
            total_lectures = 0

            # Scan lectures for this student
            for lect in lectures_def:
                col = lect.get('col_index')
                sub = lect.get('subject', 'Unknown Subject')
                time = lect.get('timing', 'Unknown Time')

                if col is None or col >= len(row):
                    continue

                val = str(row[col]).strip().upper()
                total_lectures += 1

                # Check if matches absent indicator
                is_absent = (val == absent_val) or (absent_val == 'A' and val == 'ABSENT') or (absent_val == 'ABSENT' and val == 'A') or (absent_val == 'FALSE' and val in ('FALSE', '0'))
                if is_absent:
                    absent_lectures.append({"subject": sub, "timing": time})
                else:
                    present_lectures.append({"subject": sub, "timing": time})

            # A student is categorized as "Absent" if they are absent for ANY of the lectures today
            # If there are no lectures at all, or they completed all of them, they are default Present.
            status = "Absent" if absent_lectures else "Present"

            student_details.append({
                "roll_no": roll_no,
                "name": name,
                "email": email,
                "status": status,
                "absent_lectures": absent_lectures,
                "present_lectures": present_lectures,
                "total_lectures": total_lectures
            })

        return student_details
