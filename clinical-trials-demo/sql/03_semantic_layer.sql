-- ===================================================================
-- Semantic layer: indication, sponsor, phase, status, endpoint, geography.
-- Two of these six are honest derivations rather than lookups, and the views
-- say which, because a business-facing layer that hides its own guesses is
-- worse than no layer at all.
-- ===================================================================

CREATE OR REPLACE VIEW CT.V_TRIALS AS
SELECT
  t.NCT_ID, t.INDICATION, t.BRIEF_TITLE, t.LEAD_SPONSOR,
  -- Sponsor class collapses to the distinction people actually ask about.
  CASE WHEN t.SPONSOR_CLASS = 'INDUSTRY' THEN 'Industry'
       WHEN t.SPONSOR_CLASS IN ('NIH','FED','OTHER_GOV') THEN 'Government'
       WHEN t.SPONSOR_CLASS = 'NETWORK' THEN 'Network'
       ELSE 'Academic / other' END          AS SPONSOR_TYPE,
  t.PHASE, t.PHASE_RAW,
  -- PHASE_IS_STATED exists so that "phase 3 trials" and "trials we can classify"
  -- are different questions. 22% of this snapshot has no phase.
  CASE WHEN t.PHASE = 'UNKNOWN' THEN FALSE ELSE TRUE END AS PHASE_IS_STATED,
  t.OVERALL_STATUS,
  CASE WHEN t.OVERALL_STATUS IN ('RECRUITING','NOT_YET_RECRUITING',
                                 'ENROLLING_BY_INVITATION','AVAILABLE') THEN 'Open'
       WHEN t.OVERALL_STATUS IN ('ACTIVE_NOT_RECRUITING') THEN 'Ongoing, closed to entry'
       WHEN t.OVERALL_STATUS IN ('COMPLETED') THEN 'Completed'
       WHEN t.OVERALL_STATUS IN ('TERMINATED','SUSPENDED','WITHDRAWN') THEN 'Stopped'
       ELSE 'Other' END                     AS STATUS_GROUP,
  t.ENROLLMENT, t.START_DATE,
  CASE WHEN t.START_DATE IS NULL OR t.START_DATE = '' THEN NULL
       ELSE CAST(SUBSTR(t.START_DATE, 1, 4) AS DECIMAL(4,0)) END AS START_YEAR,
  t.MIN_AGE_YEARS, t.MAX_AGE_YEARS, t.SEX, t.HEALTHY_VOLUNTEERS, t.ELIG_CHARS
FROM CT.TRIALS t;

-- ------------------------------------------------------------------
-- GEOGRAPHY. Structured and reliable; only the region rollup is ours.
-- ------------------------------------------------------------------
CREATE OR REPLACE VIEW CT.V_TRIAL_GEOGRAPHY AS
-- Country names are the API's DISPLAY names, not ISO names: it returns
-- 'South Korea', 'Turkey (Türkiye)' and 'Vietnam', not 'Korea, Republic of',
-- 'Turkey' and 'Viet Nam'. An ISO-flavoured mapping silently dumped 1,422
-- trials into 'unmapped' and under-counted Asia-Pacific by ~900. Every country
-- present in the snapshot is listed below; the ELSE is now genuinely residual.
SELECT c.NCT_ID, c.COUNTRY,
  CASE
    WHEN c.COUNTRY IN ('United States','Canada','Puerto Rico','Guam') THEN 'North America'
    WHEN c.COUNTRY IN ('China','Japan','South Korea','North Korea','Taiwan','India',
         'Hong Kong','Singapore','Thailand','Malaysia','Vietnam','Indonesia',
         'Philippines','Australia','New Zealand','Pakistan','Bangladesh','Nepal',
         'Mongolia','Kazakhstan') THEN 'Asia-Pacific'
    WHEN c.COUNTRY IN ('United Kingdom','France','Germany','Italy','Spain',
         'Netherlands','Belgium','Sweden','Denmark','Norway','Finland','Ireland',
         'Austria','Switzerland','Poland','Czechia','Hungary','Portugal','Greece',
         'Romania','Bulgaria','Slovakia','Croatia','Slovenia','Estonia','Latvia',
         'Lithuania','Luxembourg','Malta','Cyprus','Iceland','Monaco',
         'Serbia','Bosnia and Herzegovina','North Macedonia','Montenegro','Albania',
         'Russia','Ukraine','Belarus','Moldova','Georgia','Armenia','Azerbaijan')
         THEN 'Europe'
    WHEN c.COUNTRY IN ('Brazil','Argentina','Mexico','Chile','Colombia','Peru',
         'Costa Rica','Guatemala','Panama','Uruguay','Venezuela','Ecuador',
         'El Salvador','Honduras','Cuba','Dominican Republic','Jamaica',
         'Barbados','Trinidad and Tobago','Martinique') THEN 'Latin America'
    WHEN c.COUNTRY IN ('Israel','Turkey (Türkiye)','Saudi Arabia','Egypt',
         'United Arab Emirates','Lebanon','Jordan','Iran','Iraq','Qatar','Oman',
         'Bahrain','Syria','Morocco','Tunisia','Algeria','Palestinian Territories')
         THEN 'Middle East / North Africa'
    WHEN c.COUNTRY IN ('South Africa','Nigeria','Kenya','Uganda','Rwanda',
         'Botswana','Ethiopia','Ghana','Malawi','Niger') THEN 'Sub-Saharan Africa'
    ELSE 'Other / unmapped'
  END AS REGION
FROM CT.TRIAL_COUNTRIES c;

-- ------------------------------------------------------------------
-- ENDPOINT. DERIVED, not looked up. The registry gives primaryOutcomes as free
-- text (measure + timeFrame only), so there is no endpoint code to join to.
-- These patterns cover the oncology endpoints a landscape review talks about;
-- everything else falls to 'Other / unclassified', which is reported, not hidden.
-- ------------------------------------------------------------------
CREATE OR REPLACE VIEW CT.V_TRIAL_ENDPOINTS AS
SELECT o.NCT_ID, o.SEQ, o.OUTCOME_KIND, o.MEASURE, o.TIME_FRAME,
  CASE
    -- Specific efficacy endpoints first: the general RESPONSE rule below would
    -- otherwise swallow "pathological complete response" and friends.
    WHEN UPPER(o.MEASURE) REGEXP_LIKE '.*(OVERALL SURVIVAL|\bOS\b).*'                        THEN 'Overall survival'
    WHEN UPPER(o.MEASURE) REGEXP_LIKE '.*(PROGRESSION[- ]FREE SURVIVAL|\bPFS\b).*'           THEN 'Progression-free survival'
    WHEN UPPER(o.MEASURE) REGEXP_LIKE '.*(EVENT[- ]FREE SURVIVAL|DISEASE[- ]FREE SURVIVAL|RECURRENCE[- ]FREE|RELAPSE[- ]FREE|\bDFS\b|\bEFS\b|\bRFS\b).*' THEN 'Disease/event-free survival'
    WHEN UPPER(o.MEASURE) REGEXP_LIKE '.*(PATHOLOGIC(AL)? COMPLETE RESPONSE|\bPCR\b).*'      THEN 'Pathological complete response'
    WHEN UPPER(o.MEASURE) REGEXP_LIKE '.*(DURATION OF RESPONSE|\bDOR\b).*'                   THEN 'Duration of response'
    WHEN UPPER(o.MEASURE) REGEXP_LIKE '.*(DISEASE CONTROL|\bDCR\b|\bDC24\b).*'             THEN 'Disease control rate'
    WHEN UPPER(o.MEASURE) REGEXP_LIKE '.*(RELAPSE RATE|RECURRENCE RATE|LOCAL CONTROL).*'      THEN 'Relapse / local control'
    WHEN UPPER(o.MEASURE) REGEXP_LIKE '.*(DOSE[- ]LIMITING|MAXIMUM TOLERATED|\bDLT\b|\bMTD\b|RECOMMENDED PHASE).*' THEN 'Dose finding (DLT/MTD)'
    WHEN UPPER(o.MEASURE) REGEXP_LIKE '.*(ADVERSE EVENT|TOXICIT|SAFETY|TOLERABILIT).*'       THEN 'Safety / tolerability'
    WHEN UPPER(o.MEASURE) REGEXP_LIKE '.*(PHARMACOKINET|\bAUC\b|\bCMAX\b|PLASMA CONCENTRATION|SERUM CONCENTRATION).*' THEN 'Pharmacokinetics'
    WHEN UPPER(o.MEASURE) REGEXP_LIKE '.*(QUALITY OF LIFE|\bQOL\b|PATIENT[- ]REPORTED|EORTC|FACT-|\bPROMIS\b).*' THEN 'Quality of life'
    -- Non-efficacy families. These are real endpoint classes in this snapshot,
    -- not a dumping ground: behavioural, imaging and surgical trials are a third
    -- of the breast-cancer landscape and mislabelling them 'unclassified' hides that.
    WHEN UPPER(o.MEASURE) REGEXP_LIKE '.*(KNOWLEDGE|DECISION|DISTRESS|ANXIET|DEPRESS|INSOMNIA|SLEEP|FATIGUE|PAIN|SATISFACTION|WORK ABILIT).*' THEN 'Patient-reported / behavioural'
    WHEN UPPER(o.MEASURE) REGEXP_LIKE '.*(TUMOR VOLUME|TUMOUR VOLUME|IMAGING|\bMRI\b|\bPET\b|ULTRASOUND|PERFUSION|\bSUV\b|RADIOLOG|GRAYSCALE|DETECTION|SENSITIVIT|SPECIFICIT).*' THEN 'Imaging / detection'
    WHEN UPPER(o.MEASURE) REGEXP_LIKE '.*(SURGIC|SURGERY|RESECTION|MARGIN|COMPLICATION|INFECTION|RECONSTRUCTION|CAPSULAR|LYMPHEDEMA).*' THEN 'Surgical / procedural'
    WHEN UPPER(o.MEASURE) REGEXP_LIKE '.*(PLASMA|SERUM|BIOMARKER|EXPRESSION|CIRCULATING|\bCTDNA\b|\bCRP\b|INTERLEUKIN|\bIL-[0-9]|TNF|CELL COUNT|\bPD-L1\b).*' THEN 'Biomarker / laboratory'
    WHEN UPPER(o.MEASURE) REGEXP_LIKE '.*(FEASIBILIT|ACCRUAL|COMPLIANCE|ADHERENCE|UPTAKE|UTILIZATION|UTILISATION).*' THEN 'Feasibility / uptake'
    -- General response LAST, so it only catches what the specific rules missed
    -- ("Overall Response", "Clinical/pathological response", "tumor response").
    WHEN UPPER(o.MEASURE) REGEXP_LIKE '.*(OBJECTIVE RESPONSE|RESPONSE RATE|TUMOR RESPONSE|TUMOUR RESPONSE|\bORR\b|RESPONSE).*' THEN 'Objective response rate'
    ELSE 'Other / unclassified'
  END AS ENDPOINT_CATEGORY
FROM CT.TRIAL_OUTCOMES o;

-- ------------------------------------------------------------------
-- COMPARATOR. Half structured, half not -- the single best illustration of why
-- this demo needs both SQL and retrieval. armGroup.type is coded, so "is there
-- a control arm" is a WHERE clause; WHICH drug the control is sits in the arm
-- label as prose and only retrieval can reach it.
-- ------------------------------------------------------------------
CREATE OR REPLACE VIEW CT.V_TRIAL_DESIGN AS
SELECT a.NCT_ID,
       COUNT(*)                                                        AS ARM_COUNT,
       SUM(CASE WHEN a.ARM_TYPE = 'PLACEBO_COMPARATOR' THEN 1 ELSE 0 END) AS PLACEBO_ARMS,
       SUM(CASE WHEN a.ARM_TYPE = 'ACTIVE_COMPARATOR'  THEN 1 ELSE 0 END) AS ACTIVE_ARMS,
       SUM(CASE WHEN a.ARM_TYPE = 'UNSPECIFIED'        THEN 1 ELSE 0 END) AS UNTYPED_ARMS,
       CASE
         WHEN SUM(CASE WHEN a.ARM_TYPE = 'PLACEBO_COMPARATOR' THEN 1 ELSE 0 END) > 0 THEN 'Placebo-controlled'
         WHEN SUM(CASE WHEN a.ARM_TYPE = 'ACTIVE_COMPARATOR'  THEN 1 ELSE 0 END) > 0 THEN 'Active-controlled'
         WHEN COUNT(*) = 1                                                           THEN 'Single-arm'
         WHEN SUM(CASE WHEN a.ARM_TYPE = 'UNSPECIFIED' THEN 1 ELSE 0 END) = COUNT(*) THEN 'No coded comparator'
         ELSE 'Multi-arm, no control coded'
       END                                                             AS COMPARATOR_DESIGN
FROM CT.TRIAL_ARMS a
GROUP BY a.NCT_ID;

-- ------------------------------------------------------------------
-- One wide row per trial: what the agent should read first.
-- ------------------------------------------------------------------
CREATE OR REPLACE VIEW CT.V_LANDSCAPE AS
SELECT v.NCT_ID, v.INDICATION, v.BRIEF_TITLE, v.PHASE, v.PHASE_IS_STATED,
       v.STATUS_GROUP, v.OVERALL_STATUS, v.LEAD_SPONSOR, v.SPONSOR_TYPE,
       v.ENROLLMENT, v.START_YEAR, v.MIN_AGE_YEARS, v.MAX_AGE_YEARS, v.SEX,
       COALESCE(d.COMPARATOR_DESIGN, 'No arms recorded') AS COMPARATOR_DESIGN,
       d.ARM_COUNT,
       (SELECT COUNT(DISTINCT g.REGION) FROM CT.V_TRIAL_GEOGRAPHY g WHERE g.NCT_ID = v.NCT_ID) AS REGION_COUNT,
       (SELECT MIN(e.ENDPOINT_CATEGORY) FROM CT.V_TRIAL_ENDPOINTS e
         WHERE e.NCT_ID = v.NCT_ID AND e.OUTCOME_KIND = 'PRIMARY')     AS PRIMARY_ENDPOINT_CATEGORY,
       v.ELIG_CHARS
FROM CT.V_TRIALS v
LEFT JOIN CT.V_TRIAL_DESIGN d ON d.NCT_ID = v.NCT_ID;
