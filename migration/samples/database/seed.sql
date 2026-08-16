TRUNCATE TABLE interview_schedule RESTART IDENTITY CASCADE;

INSERT INTO interview_schedule (
  id,
  company_name,
  created_at,
  interview_time,
  interview_type,
  interviewer,
  meeting_link,
  notes,
  "position",
  round_number,
  status,
  updated_at
) VALUES (
  1001,
  'Comparison Corp',
  TIMESTAMP '2026-08-16 08:00:00',
  TIMESTAMP '2026-08-20 10:30:00',
  'VIDEO',
  'Baseline Interviewer',
  'https://example.invalid/meeting/1001',
  'Deterministic migration comparison fixture',
  'Backend Engineer',
  2,
  'PENDING',
  TIMESTAMP '2026-08-16 08:00:00'
);

SELECT setval(
  pg_get_serial_sequence('interview_schedule', 'id'),
  1001,
  true
);
