DELETE FROM interview_answers
WHERE session_id IN (
  SELECT id FROM interview_sessions WHERE resume_id = 2001
);
DELETE FROM interview_sessions WHERE resume_id = 2001;
DELETE FROM resume_analyses WHERE resume_id = 2001;
DELETE FROM resumes WHERE id = 2001 OR file_hash = 'resume-foundation-fixed-hash';

INSERT INTO resumes (
  id,
  access_count,
  analyze_error,
  analyze_status,
  content_type,
  file_hash,
  file_size,
  last_accessed_at,
  original_filename,
  resume_text,
  storage_key,
  storage_url,
  uploaded_at
) VALUES (
  2001,
  1,
  NULL,
  'PENDING',
  'text/plain',
  'resume-foundation-fixed-hash',
  24,
  TIMESTAMP '2026-08-16 08:00:00',
  'fixed-resume.txt',
  'Fixed resume text',
  'resumes/2026/08/16/fixed_resume.txt',
  'http://localhost:19000/interview-guide/resumes/2026/08/16/fixed_resume.txt',
  TIMESTAMP '2026-08-16 08:00:00'
);

SELECT setval(pg_get_serial_sequence('resumes', 'id'), 2001, true);
