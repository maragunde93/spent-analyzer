--
-- PostgreSQL database dump
--

\restrict jdmnf5NNTAzIrPSnas5QW1bsaaRSAzaofoNBW8JkZgdRceAeWXaEJ3TihkdoBRe

-- Dumped from database version 16.14
-- Dumped by pg_dump version 16.14

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: currency; Type: TYPE; Schema: public; Owner: spent
--

CREATE TYPE public.currency AS ENUM (
    'ARS',
    'USD'
);


ALTER TYPE public.currency OWNER TO spent;

--
-- Name: expensesource; Type: TYPE; Schema: public; Owner: spent
--

CREATE TYPE public.expensesource AS ENUM (
    'manual',
    'import_pdf',
    'bank_import',
    'cash',
    'transfer',
    'other'
);


ALTER TYPE public.expensesource OWNER TO spent;

--
-- Name: importlinekind; Type: TYPE; Schema: public; Owner: spent
--

CREATE TYPE public.importlinekind AS ENUM (
    'purchase',
    'refund',
    'payment',
    'tax',
    'fee',
    'adjustment',
    'debit_purchase',
    'cash_withdrawal',
    'card_payment',
    'transfer',
    'income',
    'previous_payment'
);


ALTER TYPE public.importlinekind OWNER TO spent;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: spent
--

CREATE TABLE public.audit_logs (
    id integer NOT NULL,
    home_group_id integer NOT NULL,
    actor_user_id integer,
    action character varying(80) NOT NULL,
    entity_type character varying(80) NOT NULL,
    entity_id integer,
    description character varying(240) NOT NULL,
    currency public.currency,
    amount numeric(14,2),
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.audit_logs OWNER TO spent;

--
-- Name: audit_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: spent
--

CREATE SEQUENCE public.audit_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.audit_logs_id_seq OWNER TO spent;

--
-- Name: audit_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: spent
--

ALTER SEQUENCE public.audit_logs_id_seq OWNED BY public.audit_logs.id;


--
-- Name: cash_wallet_entries; Type: TABLE; Schema: public; Owner: spent
--

CREATE TABLE public.cash_wallet_entries (
    id integer NOT NULL,
    home_group_id integer NOT NULL,
    user_id integer NOT NULL,
    date date NOT NULL,
    description character varying(240) NOT NULL,
    currency public.currency NOT NULL,
    amount numeric(14,2) NOT NULL,
    expense_id integer,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.cash_wallet_entries OWNER TO spent;

--
-- Name: cash_wallet_entries_id_seq; Type: SEQUENCE; Schema: public; Owner: spent
--

CREATE SEQUENCE public.cash_wallet_entries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.cash_wallet_entries_id_seq OWNER TO spent;

--
-- Name: cash_wallet_entries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: spent
--

ALTER SEQUENCE public.cash_wallet_entries_id_seq OWNED BY public.cash_wallet_entries.id;


--
-- Name: categories; Type: TABLE; Schema: public; Owner: spent
--

CREATE TABLE public.categories (
    id integer NOT NULL,
    home_group_id integer NOT NULL,
    name character varying(80) NOT NULL,
    color character varying(24) NOT NULL,
    icon character varying(40) NOT NULL,
    is_system boolean NOT NULL
);


ALTER TABLE public.categories OWNER TO spent;

--
-- Name: categories_id_seq; Type: SEQUENCE; Schema: public; Owner: spent
--

CREATE SEQUENCE public.categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.categories_id_seq OWNER TO spent;

--
-- Name: categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: spent
--

ALTER SEQUENCE public.categories_id_seq OWNED BY public.categories.id;


--
-- Name: earnings; Type: TABLE; Schema: public; Owner: spent
--

CREATE TABLE public.earnings (
    id integer NOT NULL,
    home_group_id integer NOT NULL,
    date date NOT NULL,
    description character varying(240) NOT NULL,
    user_id integer NOT NULL,
    uploaded_by_user_id integer NOT NULL,
    currency public.currency NOT NULL,
    original_amount numeric(14,2) NOT NULL,
    amount_ars numeric(14,2) NOT NULL,
    import_line_id integer,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.earnings OWNER TO spent;

--
-- Name: earnings_id_seq; Type: SEQUENCE; Schema: public; Owner: spent
--

CREATE SEQUENCE public.earnings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.earnings_id_seq OWNER TO spent;

--
-- Name: earnings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: spent
--

ALTER SEQUENCE public.earnings_id_seq OWNED BY public.earnings.id;


--
-- Name: expenses; Type: TABLE; Schema: public; Owner: spent
--

CREATE TABLE public.expenses (
    id integer NOT NULL,
    home_group_id integer NOT NULL,
    date date NOT NULL,
    description character varying(240) NOT NULL,
    category_id integer,
    subcategory_id integer,
    paid_by_user_id integer NOT NULL,
    uploaded_by_user_id integer NOT NULL,
    source public.expensesource NOT NULL,
    currency public.currency NOT NULL,
    original_amount numeric(14,2) NOT NULL,
    amount_ars numeric(14,2) NOT NULL,
    import_line_id integer,
    notes text,
    created_at timestamp without time zone NOT NULL,
    is_recurring boolean DEFAULT false NOT NULL
);


ALTER TABLE public.expenses OWNER TO spent;

--
-- Name: expenses_id_seq; Type: SEQUENCE; Schema: public; Owner: spent
--

CREATE SEQUENCE public.expenses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.expenses_id_seq OWNER TO spent;

--
-- Name: expenses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: spent
--

ALTER SEQUENCE public.expenses_id_seq OWNED BY public.expenses.id;


--
-- Name: fx_rates; Type: TABLE; Schema: public; Owner: spent
--

CREATE TABLE public.fx_rates (
    id integer NOT NULL,
    date date NOT NULL,
    source character varying(80) NOT NULL,
    from_currency public.currency NOT NULL,
    to_currency public.currency NOT NULL,
    rate numeric(14,4) NOT NULL
);


ALTER TABLE public.fx_rates OWNER TO spent;

--
-- Name: fx_rates_id_seq; Type: SEQUENCE; Schema: public; Owner: spent
--

CREATE SEQUENCE public.fx_rates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.fx_rates_id_seq OWNER TO spent;

--
-- Name: fx_rates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: spent
--

ALTER SEQUENCE public.fx_rates_id_seq OWNED BY public.fx_rates.id;


--
-- Name: home_groups; Type: TABLE; Schema: public; Owner: spent
--

CREATE TABLE public.home_groups (
    id integer NOT NULL,
    name character varying(120) NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.home_groups OWNER TO spent;

--
-- Name: home_groups_id_seq; Type: SEQUENCE; Schema: public; Owner: spent
--

CREATE SEQUENCE public.home_groups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.home_groups_id_seq OWNER TO spent;

--
-- Name: home_groups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: spent
--

ALTER SEQUENCE public.home_groups_id_seq OWNED BY public.home_groups.id;


--
-- Name: import_batches; Type: TABLE; Schema: public; Owner: spent
--

CREATE TABLE public.import_batches (
    id integer NOT NULL,
    home_group_id integer NOT NULL,
    uploaded_by_user_id integer NOT NULL,
    filename character varying(255) NOT NULL,
    source_type character varying(80) NOT NULL,
    statement_account character varying(80),
    period_label character varying(80),
    status character varying(40) NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.import_batches OWNER TO spent;

--
-- Name: import_batches_id_seq; Type: SEQUENCE; Schema: public; Owner: spent
--

CREATE SEQUENCE public.import_batches_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.import_batches_id_seq OWNER TO spent;

--
-- Name: import_batches_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: spent
--

ALTER SEQUENCE public.import_batches_id_seq OWNED BY public.import_batches.id;


--
-- Name: import_lines; Type: TABLE; Schema: public; Owner: spent
--

CREATE TABLE public.import_lines (
    id integer NOT NULL,
    import_batch_id integer NOT NULL,
    home_group_id integer NOT NULL,
    date date NOT NULL,
    description character varying(240) NOT NULL,
    coupon character varying(60),
    kind public.importlinekind NOT NULL,
    currency public.currency NOT NULL,
    original_amount numeric(14,2) NOT NULL,
    suggested_category_id integer,
    suggested_subcategory_id integer,
    status character varying(40) NOT NULL,
    fingerprint character varying(128) NOT NULL,
    raw_text text NOT NULL,
    suggested_recurring boolean DEFAULT false NOT NULL
);


ALTER TABLE public.import_lines OWNER TO spent;

--
-- Name: import_lines_id_seq; Type: SEQUENCE; Schema: public; Owner: spent
--

CREATE SEQUENCE public.import_lines_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.import_lines_id_seq OWNER TO spent;

--
-- Name: import_lines_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: spent
--

ALTER SEQUENCE public.import_lines_id_seq OWNED BY public.import_lines.id;


--
-- Name: memberships; Type: TABLE; Schema: public; Owner: spent
--

CREATE TABLE public.memberships (
    id integer NOT NULL,
    user_id integer NOT NULL,
    home_group_id integer NOT NULL,
    role character varying(40) NOT NULL
);


ALTER TABLE public.memberships OWNER TO spent;

--
-- Name: memberships_id_seq; Type: SEQUENCE; Schema: public; Owner: spent
--

CREATE SEQUENCE public.memberships_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.memberships_id_seq OWNER TO spent;

--
-- Name: memberships_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: spent
--

ALTER SEQUENCE public.memberships_id_seq OWNED BY public.memberships.id;


--
-- Name: merchants; Type: TABLE; Schema: public; Owner: spent
--

CREATE TABLE public.merchants (
    id integer NOT NULL,
    home_group_id integer NOT NULL,
    display_name character varying(160) NOT NULL,
    normalized_name character varying(160) NOT NULL,
    category_id integer,
    subcategory_id integer,
    is_recurring boolean DEFAULT false NOT NULL
);


ALTER TABLE public.merchants OWNER TO spent;

--
-- Name: merchants_id_seq; Type: SEQUENCE; Schema: public; Owner: spent
--

CREATE SEQUENCE public.merchants_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.merchants_id_seq OWNER TO spent;

--
-- Name: merchants_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: spent
--

ALTER SEQUENCE public.merchants_id_seq OWNED BY public.merchants.id;


--
-- Name: receipt_imports; Type: TABLE; Schema: public; Owner: spent
--

CREATE TABLE public.receipt_imports (
    id integer NOT NULL,
    home_group_id integer NOT NULL,
    uploaded_by_user_id integer NOT NULL,
    expense_id integer,
    filename character varying(255) NOT NULL,
    status character varying(40) NOT NULL,
    raw_text text,
    created_at timestamp without time zone NOT NULL,
    category_id integer
);


ALTER TABLE public.receipt_imports OWNER TO spent;

--
-- Name: receipt_imports_id_seq; Type: SEQUENCE; Schema: public; Owner: spent
--

CREATE SEQUENCE public.receipt_imports_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.receipt_imports_id_seq OWNER TO spent;

--
-- Name: receipt_imports_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: spent
--

ALTER SEQUENCE public.receipt_imports_id_seq OWNED BY public.receipt_imports.id;


--
-- Name: receipt_items; Type: TABLE; Schema: public; Owner: spent
--

CREATE TABLE public.receipt_items (
    id integer NOT NULL,
    receipt_import_id integer NOT NULL,
    description character varying(240) NOT NULL,
    quantity numeric(14,3),
    unit_price numeric(14,2),
    total_amount numeric(14,2) NOT NULL,
    status character varying(40) DEFAULT 'accepted'::character varying NOT NULL,
    subcategory_id integer,
    suggested_subcategory_name character varying(80)
);


ALTER TABLE public.receipt_items OWNER TO spent;

--
-- Name: receipt_items_id_seq; Type: SEQUENCE; Schema: public; Owner: spent
--

CREATE SEQUENCE public.receipt_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.receipt_items_id_seq OWNER TO spent;

--
-- Name: receipt_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: spent
--

ALTER SEQUENCE public.receipt_items_id_seq OWNED BY public.receipt_items.id;


--
-- Name: recurring_rules; Type: TABLE; Schema: public; Owner: spent
--

CREATE TABLE public.recurring_rules (
    id integer NOT NULL,
    home_group_id integer NOT NULL,
    description_pattern character varying(160) NOT NULL,
    category_id integer,
    currency public.currency NOT NULL,
    expected_amount numeric(14,2),
    cadence character varying(40) NOT NULL,
    active boolean NOT NULL
);


ALTER TABLE public.recurring_rules OWNER TO spent;

--
-- Name: recurring_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: spent
--

CREATE SEQUENCE public.recurring_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.recurring_rules_id_seq OWNER TO spent;

--
-- Name: recurring_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: spent
--

ALTER SEQUENCE public.recurring_rules_id_seq OWNED BY public.recurring_rules.id;


--
-- Name: subcategories; Type: TABLE; Schema: public; Owner: spent
--

CREATE TABLE public.subcategories (
    id integer NOT NULL,
    home_group_id integer NOT NULL,
    category_id integer NOT NULL,
    name character varying(80) NOT NULL,
    is_system boolean NOT NULL
);


ALTER TABLE public.subcategories OWNER TO spent;

--
-- Name: subcategories_id_seq; Type: SEQUENCE; Schema: public; Owner: spent
--

CREATE SEQUENCE public.subcategories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.subcategories_id_seq OWNER TO spent;

--
-- Name: subcategories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: spent
--

ALTER SEQUENCE public.subcategories_id_seq OWNED BY public.subcategories.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: spent
--

CREATE TABLE public.users (
    id integer NOT NULL,
    email character varying(255) NOT NULL,
    display_name character varying(120) NOT NULL,
    google_sub character varying(255),
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.users OWNER TO spent;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: spent
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO spent;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: spent
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: audit_logs id; Type: DEFAULT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.audit_logs ALTER COLUMN id SET DEFAULT nextval('public.audit_logs_id_seq'::regclass);


--
-- Name: cash_wallet_entries id; Type: DEFAULT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.cash_wallet_entries ALTER COLUMN id SET DEFAULT nextval('public.cash_wallet_entries_id_seq'::regclass);


--
-- Name: categories id; Type: DEFAULT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.categories ALTER COLUMN id SET DEFAULT nextval('public.categories_id_seq'::regclass);


--
-- Name: earnings id; Type: DEFAULT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.earnings ALTER COLUMN id SET DEFAULT nextval('public.earnings_id_seq'::regclass);


--
-- Name: expenses id; Type: DEFAULT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.expenses ALTER COLUMN id SET DEFAULT nextval('public.expenses_id_seq'::regclass);


--
-- Name: fx_rates id; Type: DEFAULT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.fx_rates ALTER COLUMN id SET DEFAULT nextval('public.fx_rates_id_seq'::regclass);


--
-- Name: home_groups id; Type: DEFAULT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.home_groups ALTER COLUMN id SET DEFAULT nextval('public.home_groups_id_seq'::regclass);


--
-- Name: import_batches id; Type: DEFAULT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.import_batches ALTER COLUMN id SET DEFAULT nextval('public.import_batches_id_seq'::regclass);


--
-- Name: import_lines id; Type: DEFAULT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.import_lines ALTER COLUMN id SET DEFAULT nextval('public.import_lines_id_seq'::regclass);


--
-- Name: memberships id; Type: DEFAULT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.memberships ALTER COLUMN id SET DEFAULT nextval('public.memberships_id_seq'::regclass);


--
-- Name: merchants id; Type: DEFAULT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.merchants ALTER COLUMN id SET DEFAULT nextval('public.merchants_id_seq'::regclass);


--
-- Name: receipt_imports id; Type: DEFAULT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.receipt_imports ALTER COLUMN id SET DEFAULT nextval('public.receipt_imports_id_seq'::regclass);


--
-- Name: receipt_items id; Type: DEFAULT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.receipt_items ALTER COLUMN id SET DEFAULT nextval('public.receipt_items_id_seq'::regclass);


--
-- Name: recurring_rules id; Type: DEFAULT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.recurring_rules ALTER COLUMN id SET DEFAULT nextval('public.recurring_rules_id_seq'::regclass);


--
-- Name: subcategories id; Type: DEFAULT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.subcategories ALTER COLUMN id SET DEFAULT nextval('public.subcategories_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Data for Name: audit_logs; Type: TABLE DATA; Schema: public; Owner: spent
--

COPY public.audit_logs (id, home_group_id, actor_user_id, action, entity_type, entity_id, description, currency, amount, created_at) FROM stdin;
1	1	1	import_upload	import_batch	1	Resumen de tarjeta cargado: Resumen.pdf	\N	\N	2026-07-06 17:56:25.51422
2	1	1	import_upload	import_batch	2	Resumen de tarjeta cargado: Resumen (1).pdf	\N	\N	2026-07-06 17:56:31.083481
3	1	1	import_upload	import_batch	3	Resumen de tarjeta cargado: Resumen (2).pdf	\N	\N	2026-07-06 17:56:33.99455
4	1	1	import_upload	import_batch	4	Resumen de tarjeta cargado: Resumen (3).pdf	\N	\N	2026-07-06 17:56:37.071744
5	1	1	import_upload	import_batch	5	Resumen de tarjeta cargado: Resumen (4).pdf	\N	\N	2026-07-06 17:56:39.794444
6	1	1	category_create	category	16	Herramientas	\N	\N	2026-07-06 17:59:27.614329
7	1	1	category_update	category	16	Herramientas	\N	\N	2026-07-06 17:59:40.194278
8	1	1	subcategory_create	subcategory	22	Bebida alcholica	\N	\N	2026-07-06 18:00:50.469569
9	1	1	category_create	category	17	Mascotas	\N	\N	2026-07-06 18:01:05.462706
10	1	1	import_commit	import_batch	5	Importacion procesada: 21 lineas, 21 gastos creados	\N	\N	2026-07-06 18:04:11.041119
11	1	1	subcategory_create	subcategory	23	Pileta	\N	\N	2026-07-06 18:04:34.154297
12	1	1	subcategory_create	subcategory	24	Repuestos	\N	\N	2026-07-06 18:04:41.378352
13	1	1	subcategory_create	subcategory	25	Electrodomestico	\N	\N	2026-07-06 18:04:46.893437
14	1	1	subcategory_create	subcategory	26	Banco	\N	\N	2026-07-06 18:06:20.866401
15	1	1	expense_update	expense	20	COMISION CTA PWORLD	ARS	61157.02	2026-07-06 18:06:29.595745
16	1	1	expense_update	expense	17	SANITARIOS VAL-MAR	ARS	58862.96	2026-07-06 18:06:41.335567
17	1	1	expense_update	expense	13	MERPAGO*MUNDOFIX C.01/02	ARS	54999.50	2026-07-06 18:07:01.978113
18	1	1	expense_update	expense	11	MERPAGO*REX	ARS	100056.45	2026-07-06 18:07:12.903845
19	1	1	expense_update	expense	8	DISCO SM 037	ARS	76206.22	2026-07-06 18:07:28.642682
20	1	1	expense_update	expense	7	MERPAGO*MERCADOLIBRE	ARS	64072.00	2026-07-06 18:07:38.625544
21	1	1	expense_update	expense	3	MERPAGO*GAEDSH	ARS	28755.99	2026-07-06 18:07:56.25498
22	1	1	subcategory_create	subcategory	27	Alimento	\N	\N	2026-07-06 18:08:12.903734
23	1	1	subcategory_create	subcategory	28	Piedras	\N	\N	2026-07-06 18:08:15.88129
24	1	1	subcategory_create	subcategory	29	Veterinaria	\N	\N	2026-07-06 18:08:18.067193
25	1	1	subcategory_create	subcategory	30	Juguetes	\N	\N	2026-07-06 18:08:21.03813
26	1	1	subcategory_create	subcategory	31	Otros	\N	\N	2026-07-06 18:08:25.68919
27	1	1	subcategory_create	subcategory	32	Combustible	\N	\N	2026-07-06 18:12:22.911853
28	1	1	import_commit	import_batch	4	Importacion procesada: 28 lineas, 28 gastos creados	\N	\N	2026-07-06 18:15:49.740971
29	1	1	expense_update	expense	22	MERPAGO*MERCADOLIBRE C.03/06	ARS	9998.33	2026-07-06 18:17:04.896279
30	1	1	import_delete	import_batch	3	Importacion borrada: Resumen (2).pdf	\N	\N	2026-07-06 18:33:58.233038
31	1	1	import_delete	import_batch	2	Importacion borrada: Resumen (1).pdf	\N	\N	2026-07-06 18:33:59.53767
32	1	1	import_delete	import_batch	1	Importacion borrada: Resumen.pdf	\N	\N	2026-07-06 18:34:00.41055
33	1	1	import_upload	import_batch	6	Resumen de tarjeta cargado: Resumen (1).pdf	\N	\N	2026-07-06 18:34:06.999894
34	1	1	subcategory_create	subcategory	33	Juego  PC	\N	\N	2026-07-06 18:34:44.156716
35	1	1	subcategory_create	subcategory	34	Salida	\N	\N	2026-07-06 18:35:03.468602
36	1	1	subcategory_create	subcategory	35	Libro	\N	\N	2026-07-06 18:35:06.843877
37	1	1	import_commit	import_batch	6	Importacion procesada: 53 lineas, 53 gastos creados	\N	\N	2026-07-06 18:40:38.431741
38	1	1	expense_update	expense	52	MERPAGO*HERTZARG	ARS	463247.64	2026-07-06 18:41:25.266964
39	1	1	expense_update	expense	63	MERPAGO*PARQUEGAS	ARS	447039.12	2026-07-06 18:41:46.204684
40	1	1	expense_update	expense	52	MERPAGO*HERTZARG	ARS	463247.64	2026-07-06 18:41:48.530657
41	1	1	expense_update	expense	73	MERPAGO*TCTIENDAS	ARS	83930.00	2026-07-06 18:42:04.050077
42	1	1	import_upload	import_batch	7	Resumen de tarjeta cargado: Resumen (1).pdf	\N	\N	2026-07-06 18:42:22.323333
43	1	1	import_delete	import_batch	7	Importacion borrada: Resumen (1).pdf	\N	\N	2026-07-06 18:42:27.405701
44	1	1	import_upload	import_batch	8	Resumen de tarjeta cargado: Resumen.pdf	\N	\N	2026-07-06 18:42:29.124298
45	1	1	import_commit	import_batch	8	Importacion procesada: 47 lineas, 47 gastos creados	\N	\N	2026-07-06 18:44:31.142593
46	1	1	import_upload	import_batch	9	Resumen de tarjeta cargado: Resumen.pdf	\N	\N	2026-07-06 18:45:27.988273
47	1	1	import_delete	import_batch	9	Importacion borrada: Resumen.pdf	\N	\N	2026-07-06 18:45:32.086563
48	1	1	import_upload	import_batch	10	Movimientos de cuenta cargados: Detalle_mov_cuenta_03_07_2026 (2).xls	\N	\N	2026-07-06 18:45:38.791098
49	1	1	import_delete	import_batch	10	Importacion borrada: Detalle_mov_cuenta_03_07_2026 (2).xls	\N	\N	2026-07-06 18:45:47.479914
50	1	1	import_upload	import_batch	11	Resumen de tarjeta cargado: Resumen (2).pdf	\N	\N	2026-07-06 18:46:47.267447
51	1	1	import_commit	import_batch	11	Importacion procesada: 36 lineas, 36 gastos creados	\N	\N	2026-07-06 18:48:10.428794
52	1	1	import_upload	import_batch	12	Resumen de tarjeta cargado: Resumen.pdf	\N	\N	2026-07-06 18:50:21.455937
53	1	1	import_upload	import_batch	13	Movimientos de cuenta cargados: Detalle_mov_cuenta_03_07_2026 (2).xls	\N	\N	2026-07-06 18:53:56.205153
54	1	1	import_delete	import_batch	12	Importacion borrada: Resumen.pdf	\N	\N	2026-07-06 18:54:46.094921
55	1	1	import_delete	import_batch	13	Importacion borrada: Detalle_mov_cuenta_03_07_2026 (2).xls	\N	\N	2026-07-06 18:54:48.065365
56	1	1	import_upload	import_batch	14	Movimientos de cuenta cargados: Detalle_mov_cuenta_06_07_2026.xls	\N	\N	2026-07-06 18:54:51.218672
57	1	1	import_commit	import_batch	14	Importacion procesada: 62 lineas, 42 gastos creados	\N	\N	2026-07-06 19:15:56.788967
\.


--
-- Data for Name: cash_wallet_entries; Type: TABLE DATA; Schema: public; Owner: spent
--

COPY public.cash_wallet_entries (id, home_group_id, user_id, date, description, currency, amount, expense_id, created_at) FROM stdin;
\.


--
-- Data for Name: categories; Type: TABLE DATA; Schema: public; Owner: spent
--

COPY public.categories (id, home_group_id, name, color, icon, is_system) FROM stdin;
10	1	Transporte	#9c27b0	car	t
11	1	Ocio / gasto personal	#7c4dff	gamepad	t
14	1	Vestimenta	#e91e63	shirt	t
15	1	Regalos	#ff5722	gift	t
2	1	Compras del hogar	#2171b5	shopping-cart	t
16	1	Herramientas	#3af8c8	tag	f
17	1	Mascotas	#20d556	tag	f
1	1	Delivery	#41b6e6	utensils	t
3	1	Servicios	#ff9800	receipt	t
4	1	Impuestos	#795548	landmark	t
6	1	Salud	#009688	heart-pulse	t
7	1	Auto	#607d8b	car-front	t
8	1	Suscripciones	#ffc107	repeat	t
9	1	Vacaciones	#4caf50	plane	t
13	1	Sin categoria	#f44336	tag	t
\.


--
-- Data for Name: earnings; Type: TABLE DATA; Schema: public; Owner: spent
--

COPY public.earnings (id, home_group_id, date, description, user_id, uploaded_by_user_id, currency, original_amount, amount_ars, import_line_id, created_at) FROM stdin;
1	1	2026-07-01	INTERESES GANADOS	1	1	ARS	37.60	37.60	571	2026-07-06 19:15:56.543362
2	1	2026-06-22	TRANSFERENCIA	1	1	ARS	115000.00	115000.00	576	2026-07-06 19:15:56.569631
3	1	2026-06-17	TRANSF. CLIENTE CTA. CAP027 027024 8 Nro:00010008	1	1	ARS	290800.00	290800.00	578	2026-07-06 19:15:56.577724
4	1	2026-06-05	TRANSFERENCIA CCP316 316621 5	1	1	ARS	49174.99	49174.99	588	2026-07-06 19:15:56.604116
5	1	2026-06-01	REINTEGRO PROMO BBVA. 20% en Disco &	1	1	ARS	25000.00	25000.00	592	2026-07-06 19:15:56.604119
6	1	2026-06-01	INTERESES GANADOS	1	1	ARS	16.92	16.92	593	2026-07-06 19:15:56.60412
7	1	2026-05-19	TRANSFERENCIA	1	1	ARS	82600.00	82600.00	597	2026-07-06 19:15:56.625307
8	1	2026-05-04	INTERESES GANADOS	1	1	ARS	19.09	19.09	602	2026-07-06 19:15:56.633558
9	1	2026-04-27	TRANSFERENCIA	1	1	ARS	24000.00	24000.00	606	2026-07-06 19:15:56.652867
10	1	2026-04-27	TRANSF. CLIENTE CTA. CAP999 277484 1 Nro:00010008	1	1	ARS	12000.00	12000.00	607	2026-07-06 19:15:56.65287
11	1	2026-04-06	REINTEGRO PROMO BBVA. 20% en Disco &	1	1	ARS	25000.00	25000.00	624	2026-07-06 19:15:56.704778
12	1	2026-04-01	INTERESES GANADOS	1	1	ARS	32.05	32.05	625	2026-07-06 19:15:56.704781
13	1	2026-03-27	GESTION PAGO	1	1	ARS	3061.27	3061.27	626	2026-07-06 19:15:56.704781
14	1	2026-03-25	TRANSFERENCIA	1	1	ARS	6000.00	6000.00	628	2026-07-06 19:15:56.715764
15	1	2026-03-25	TRANSFERENCIA	1	1	ARS	88000.00	88000.00	629	2026-07-06 19:15:56.720134
16	1	2026-03-20	TRANSFERENCIA	1	1	ARS	143585.00	143585.00	631	2026-07-06 19:15:56.727955
17	1	2026-03-02	INTERESES GANADOS	1	1	ARS	23.91	23.91	640	2026-07-06 19:15:56.74788
18	1	2026-02-19	TRANSFERENCIA	1	1	ARS	24400.00	24400.00	645	2026-07-06 19:15:56.757096
19	1	2026-02-18	TRANSF. CLIENTE CTA. CAP184 311532 8 Nro:00010008	1	1	ARS	32300.00	32300.00	647	2026-07-06 19:15:56.766574
20	1	2026-02-18	TRANSF. CLIENTE CTA. CAP316 427769 9 Nro:00010008	1	1	ARS	32500.00	32500.00	648	2026-07-06 19:15:56.766576
\.


--
-- Data for Name: expenses; Type: TABLE DATA; Schema: public; Owner: spent
--

COPY public.expenses (id, home_group_id, date, description, category_id, subcategory_id, paid_by_user_id, uploaded_by_user_id, source, currency, original_amount, amount_ars, import_line_id, notes, created_at, is_recurring) FROM stdin;
1	1	2026-01-29	PLATEANET C.03/03	11	\N	1	1	import_pdf	ARS	96000.00	96000.00	173	\N	2026-07-06 18:04:10.973845	f
2	1	2026-01-29	MERPAGO*MERCADOLIBRE C.02/06	11	\N	1	1	import_pdf	ARS	9998.33	9998.33	174	\N	2026-07-06 18:04:10.977901	f
4	1	2026-01-03	DLO*PEDIDOSYA PLUS	1	\N	1	1	import_pdf	ARS	5490.00	5490.00	176	\N	2026-07-06 18:04:10.984335	f
5	1	2026-01-04	MERPAGO*TADA	2	22	1	1	import_pdf	ARS	68550.00	68550.00	177	\N	2026-07-06 18:04:10.987355	f
6	1	2026-01-05	PEDIDOSYA*GLORIOSO CHUR	1	\N	1	1	import_pdf	ARS	11390.00	11390.00	178	\N	2026-07-06 18:04:10.991002	f
7	1	2026-01-06	MERPAGO*MERCADOLIBRE	17	\N	1	1	import_pdf	ARS	64072.00	64072.00	179	\N	2026-07-06 18:04:10.993795	f
8	1	2026-01-06	DISCO SM 037	2	\N	1	1	import_pdf	ARS	76206.22	76206.22	180	\N	2026-07-06 18:04:10.997151	f
9	1	2026-01-08	MOVISTAR HOGAR 000000568729017	3	5	1	1	import_pdf	ARS	42209.99	42209.99	181	\N	2026-07-06 18:04:11.000177	t
10	1	2026-01-10	PEDIDOSYA*HARRYS KILLER	1	\N	1	1	import_pdf	ARS	17390.00	17390.00	182	\N	2026-07-06 18:04:11.003664	f
12	1	2026-01-13	EDESUR	3	1	1	1	import_pdf	ARS	278614.46	278614.46	184	\N	2026-07-06 18:04:11.009659	f
14	1	2026-01-15	PEDIDOSYA*KFC ADROGUE	1	\N	1	1	import_pdf	ARS	27610.00	27610.00	186	\N	2026-07-06 18:04:11.015353	f
15	1	2026-01-16	CLARO DEB AUT 000021326330519	3	5	1	1	import_pdf	ARS	23066.99	23066.99	187	\N	2026-07-06 18:04:11.018263	t
16	1	2026-01-16	METROGAS SA DEB 020307417400	3	3	1	1	import_pdf	ARS	40011.88	40011.88	188	\N	2026-07-06 18:04:11.021679	t
18	1	2026-01-20	CAJA SEG-PROMO BB023838068 -0	7	7	1	1	import_pdf	ARS	184669.00	184669.00	190	\N	2026-07-06 18:04:11.027647	f
19	1	2026-01-26	OSDE 000062938930501	6	\N	1	1	import_pdf	ARS	159659.44	159659.44	191	\N	2026-07-06 18:04:11.030975	f
21	1	2026-01-29	DB IVA $ 21% 61.157,02	4	\N	1	1	import_pdf	ARS	12842.97	12842.97	193	\N	2026-07-06 18:04:11.037069	f
17	1	2026-01-19	SANITARIOS VAL-MAR	2	24	1	1	import_pdf	ARS	58862.96	58862.96	189	\N	2026-07-06 18:04:11.024492	f
13	1	2026-01-29	MERPAGO*MUNDOFIX C.01/02	2	25	1	1	import_pdf	ARS	54999.50	54999.50	185	Mini pimer	2026-07-06 18:04:11.012186	f
11	1	2026-01-13	MERPAGO*REX	2	23	1	1	import_pdf	ARS	100056.45	100056.45	183	Cloro	2026-07-06 18:04:11.007224	f
3	1	2026-01-02	MERPAGO*GAEDSH	16	\N	1	1	import_pdf	ARS	28755.99	28755.99	175	Llave cinta para caños	2026-07-06 18:04:10.980909	f
23	1	2026-02-26	MERPAGO*MUNDOFIX C.02/02	2	25	1	1	import_pdf	ARS	54999.50	54999.50	144	\N	2026-07-06 18:15:49.626439	f
24	1	2026-02-26	MERPAGO*KAMADOARGENTI C.01/03	2	14	1	1	import_pdf	ARS	14412.34	14412.34	145	\N	2026-07-06 18:15:49.629188	f
25	1	2026-01-31	PEDIDOSYA*HARRYS KILLER	1	\N	1	1	import_pdf	ARS	36150.00	36150.00	146	\N	2026-07-06 18:15:49.632356	f
26	1	2026-02-03	DLO*PEDIDOSYA PLUS	1	\N	1	1	import_pdf	ARS	5490.00	5490.00	147	\N	2026-07-06 18:15:49.636112	f
27	1	2026-02-26	MERPAGO*KAMADOARGENTI C.01/06	2	14	1	1	import_pdf	ARS	31083.50	31083.50	148	\N	2026-07-06 18:15:49.638829	f
28	1	2026-02-04	COTO SUCURSAL 107	2	\N	1	1	import_pdf	ARS	455750.07	455750.07	149	\N	2026-07-06 18:15:49.641679	f
29	1	2026-02-08	MERPAGO*EUPRO	11	\N	1	1	import_pdf	ARS	50228.93	50228.93	150	\N	2026-07-06 18:15:49.643982	f
30	1	2026-02-09	MERPAGO*MERCADOLIBRE	2	14	1	1	import_pdf	ARS	142941.51	142941.51	151	\N	2026-07-06 18:15:49.646532	f
31	1	2026-02-10	DLO*PEDIDOSYA PROPINA	1	\N	1	1	import_pdf	ARS	650.00	650.00	152	\N	2026-07-06 18:15:49.650157	f
32	1	2026-02-10	PEDIDOSYA*HARRYS KILLER	1	\N	1	1	import_pdf	ARS	18190.00	18190.00	153	\N	2026-07-06 18:15:49.68539	f
33	1	2026-02-10	MOVISTAR HOGAR 000000568729017	3	5	1	1	import_pdf	ARS	43259.99	43259.99	154	\N	2026-07-06 18:15:49.689729	t
34	1	2026-02-11	EDESUR	3	1	1	1	import_pdf	ARS	111095.37	111095.37	155	\N	2026-07-06 18:15:49.692714	t
35	1	2026-02-13	DLO*PEDIDOSYA PROPINA	1	\N	1	1	import_pdf	ARS	700.00	700.00	156	\N	2026-07-06 18:15:49.69677	f
36	1	2026-02-13	PEDIDOSYA*LUCCIANOS ADR	1	\N	1	1	import_pdf	ARS	26430.00	26430.00	157	\N	2026-07-06 18:15:49.700182	f
37	1	2026-02-26	MERPAGO*SOHODENIMROPA C.01/03	14	\N	1	1	import_pdf	ARS	40186.68	40186.68	158	\N	2026-07-06 18:15:49.702749	f
38	1	2026-02-17	CLARO DEB AUT 000021326330519	3	5	1	1	import_pdf	ARS	24103.75	24103.75	159	\N	2026-07-06 18:15:49.705752	t
39	1	2026-02-18	SHELL ADROGUE	7	32	1	1	import_pdf	ARS	98000.00	98000.00	160	\N	2026-07-06 18:15:49.708241	f
40	1	2026-02-19	METROGAS SA DEB 020307417400	3	3	1	1	import_pdf	ARS	37228.78	37228.78	161	\N	2026-07-06 18:15:49.711561	t
41	1	2026-02-19	CAJA SEG-PROMO BB023838068 -0	7	7	1	1	import_pdf	ARS	190832.00	190832.00	162	\N	2026-07-06 18:15:49.714669	t
42	1	2026-02-20	MERPAGO*MERCADOLIBRE	11	\N	1	1	import_pdf	ARS	86627.00	86627.00	163	\N	2026-07-06 18:15:49.717611	f
43	1	2026-02-20	MERPAGO*CMORRES	2	20	1	1	import_pdf	ARS	75485.83	75485.83	164	\N	2026-07-06 18:15:49.720574	f
44	1	2026-02-20	DISCO SM 037	2	\N	1	1	import_pdf	ARS	80750.83	80750.83	165	\N	2026-07-06 18:15:49.723605	f
45	1	2026-02-26	MERPAGO*ACIUM C.01/03	13	\N	1	1	import_pdf	ARS	69333.34	69333.34	166	\N	2026-07-06 18:15:49.725861	f
46	1	2026-02-22	PEDIDOSYA*LUCCIANOS ADR	1	\N	1	1	import_pdf	ARS	31860.00	31860.00	167	\N	2026-07-06 18:15:49.72868	f
47	1	2026-02-24	OSDE 000062938930501	6	\N	1	1	import_pdf	ARS	157645.00	157645.00	168	\N	2026-07-06 18:15:49.731437	f
49	1	2026-02-26	DB IVA $ 21% 61.157,02	4	\N	1	1	import_pdf	ARS	12842.97	12842.97	170	\N	2026-07-06 18:15:49.737508	f
22	1	2026-02-26	MERPAGO*MERCADOLIBRE C.03/06	11	\N	1	1	import_pdf	ARS	9998.33	9998.33	143	Rummy	2026-07-06 18:15:49.62381	f
20	1	2025-12-31	COMISION CTA PWORLD	3	26	1	1	import_pdf	ARS	61157.02	61157.02	192	\N	2026-07-06 18:04:11.033977	f
48	1	2026-01-29	COMISION CTA PWORLD	3	26	1	1	import_pdf	ARS	61157.02	61157.02	169	\N	2026-07-06 18:15:49.734632	f
50	1	2026-04-09	CR.RG 5617 30% M	4	\N	1	1	import_pdf	ARS	-6194.61	-6194.61	196	\N	2026-07-06 18:40:38.233999	f
51	1	2026-04-08	IGUAZU ARGENTINA SA	9	\N	1	1	import_pdf	ARS	190000.00	190000.00	197	\N	2026-07-06 18:40:38.2404	f
53	1	2026-04-30	MERPAGO*MERCADOLIBRE C.05/06	11	\N	1	1	import_pdf	ARS	9998.33	9998.33	199	\N	2026-07-06 18:40:38.25134	f
54	1	2026-04-30	MERPAGO*KAMADOARGENTI C.03/03	2	14	1	1	import_pdf	ARS	14412.33	14412.33	200	\N	2026-07-06 18:40:38.255554	f
55	1	2026-04-30	MERPAGO*KAMADOARGENTI C.03/06	2	14	1	1	import_pdf	ARS	31083.50	31083.50	201	\N	2026-07-06 18:40:38.260479	f
56	1	2026-04-30	MERPAGO*SOHODENIMROPA C.03/03	14	\N	1	1	import_pdf	ARS	40186.66	40186.66	202	\N	2026-07-06 18:40:38.265881	f
57	1	2026-04-30	MERPAGO*ACIUM C.03/03	13	\N	1	1	import_pdf	ARS	69333.33	69333.33	203	\N	2026-07-06 18:40:38.27046	f
58	1	2026-03-29	DLO*PEDIDOSYA PROPINA	1	\N	1	1	import_pdf	ARS	200.00	200.00	204	\N	2026-07-06 18:40:38.27461	f
52	1	2026-04-14	MERPAGO*HERTZARG	9	\N	1	1	import_pdf	ARS	463247.64	463247.64	198	\N	2026-07-06 18:40:38.247055	f
59	1	2026-03-29	PEDIDOSYA*TEQUESUR	1	\N	1	1	import_pdf	ARS	14310.00	14310.00	205	\N	2026-07-06 18:40:38.278496	f
60	1	2026-03-29	PEDIDOSYA*KFC ADROGUE	1	\N	1	1	import_pdf	ARS	17410.00	17410.00	206	\N	2026-07-06 18:40:38.282456	f
61	1	2026-03-31	MERPAGO*PELONLINE	2	13	1	1	import_pdf	ARS	38340.00	38340.00	207	\N	2026-07-06 18:40:38.286502	f
62	1	2026-03-31	MERPAGO*MERCADOLIBRE	11	\N	1	1	import_pdf	ARS	40948.99	40948.99	208	\N	2026-07-06 18:40:38.292275	f
64	1	2026-04-03	DLO*PEDIDOSYA PLUS	1	\N	1	1	import_pdf	ARS	5990.00	5990.00	210	\N	2026-07-06 18:40:38.298746	f
65	1	2026-04-04	MERPAGO*CMORRES	2	20	1	1	import_pdf	ARS	71279.40	71279.40	211	\N	2026-07-06 18:40:38.302566	f
66	1	2026-04-05	DISCO SM 037 MODO	2	\N	1	1	import_pdf	ARS	164600.18	164600.18	212	\N	2026-07-06 18:40:38.306153	f
67	1	2026-04-09	MOVISTAR HOGAR 000000568729017	3	5	1	1	import_pdf	ARS	46307.98	46307.98	213	\N	2026-07-06 18:40:38.308579	t
68	1	2026-04-09	WL *Steam Purchase	11	33	1	1	import_pdf	USD	20.09	20090.00	214	\N	2026-07-06 18:40:38.315942	f
69	1	2026-04-10	MERPAGO*CMORRES	2	20	1	1	import_pdf	ARS	99034.18	99034.18	215	\N	2026-07-06 18:40:38.322407	f
70	1	2026-04-11	DIA TIENDA 5556	2	10	1	1	import_pdf	ARS	3785.00	3785.00	216	\N	2026-07-06 18:40:38.325518	f
71	1	2026-04-12	Crunchyroll LLC	8	\N	1	1	import_pdf	ARS	7379.79	7379.79	217	\N	2026-07-06 18:40:38.329135	f
72	1	2026-04-12	PEDIDOSYA*DER GRUND TEM	1	\N	1	1	import_pdf	ARS	42480.00	42480.00	218	\N	2026-07-06 18:40:38.332391	f
74	1	2026-04-13	SHELL	7	32	1	1	import_pdf	ARS	117000.00	117000.00	220	\N	2026-07-06 18:40:38.341003	f
75	1	2026-04-15	WL *Steam Purchase	11	33	1	1	import_pdf	USD	11.99	11990.00	221	\N	2026-07-06 18:40:38.34472	f
76	1	2026-04-16	MERPAGO*CMORRES	2	20	1	1	import_pdf	ARS	52227.35	52227.35	222	\N	2026-07-06 18:40:38.349338	f
77	1	2026-04-16	DISCO SM 037	2	\N	1	1	import_pdf	ARS	95440.00	95440.00	223	\N	2026-07-06 18:40:38.352085	f
78	1	2026-04-16	PEDIDOSYA*PERTUTTI ADRO	1	\N	1	1	import_pdf	ARS	40580.00	40580.00	224	\N	2026-07-06 18:40:38.355123	f
79	1	2026-04-17	CLARO DEB AUT 000021326330519	3	5	1	1	import_pdf	ARS	26039.76	26039.76	225	\N	2026-07-06 18:40:38.357368	t
80	1	2026-04-17	PEDIDOSYA*TIENDA DE CAF	1	\N	1	1	import_pdf	ARS	21430.00	21430.00	226	\N	2026-07-06 18:40:38.360384	f
81	1	2026-04-17	AMAZON PRIME*DU0 18CsiyApr	8	\N	1	1	import_pdf	USD	14.99	14990.00	227	\N	2026-07-06 18:40:38.363526	t
82	1	2026-04-19	STEAMGAMES.COM 4259522985	11	33	1	1	import_pdf	USD	8.99	8990.00	228	\N	2026-07-06 18:40:38.366742	f
83	1	2026-04-20	METROGAS SA DEB 020307417400	3	3	1	1	import_pdf	ARS	42313.52	42313.52	229	\N	2026-07-06 18:40:38.36997	t
84	1	2026-04-21	CAJA SEG-PROMO BB023838068 -0	7	7	1	1	import_pdf	ARS	201755.00	201755.00	230	\N	2026-07-06 18:40:38.372328	t
85	1	2026-04-21	DLO*PEDIDOSYA PROPINA	1	\N	1	1	import_pdf	ARS	300.00	300.00	231	\N	2026-07-06 18:40:38.375478	f
86	1	2026-04-21	PEDIDOSYA*CUQUET HOUSE	1	\N	1	1	import_pdf	ARS	13420.00	13420.00	232	\N	2026-07-06 18:40:38.37847	f
87	1	2026-04-23	DLO*PEDIDOSYA PROPINA	1	\N	1	1	import_pdf	ARS	650.00	650.00	233	\N	2026-07-06 18:40:38.381068	f
88	1	2026-04-23	PEDIDOSYA*THOUSAND BURG	1	\N	1	1	import_pdf	ARS	20720.00	20720.00	234	\N	2026-07-06 18:40:38.383891	f
89	1	2026-04-25	STARBUCKS PORTAL LOMAS	11	34	1	1	import_pdf	ARS	43200.00	43200.00	235	\N	2026-07-06 18:40:38.387826	f
90	1	2026-04-25	OSDE 000062938930501	6	\N	1	1	import_pdf	ARS	195211.21	195211.21	236	\N	2026-07-06 18:40:38.39088	f
91	1	2026-04-26	EDESUR	3	1	1	1	import_pdf	ARS	100895.35	100895.35	237	\N	2026-07-06 18:40:38.393167	t
92	1	2026-04-26	DLO*PEDIDOSYA PROPINA	1	\N	1	1	import_pdf	ARS	400.00	400.00	238	\N	2026-07-06 18:40:38.396053	f
93	1	2026-04-26	PEDIDOSYA*PERTUTTI ADRO	1	\N	1	1	import_pdf	ARS	46580.00	46580.00	239	\N	2026-07-06 18:40:38.399473	f
94	1	2026-04-26	PEDIDOSYA*LAS MEDIALUNA	1	\N	1	1	import_pdf	ARS	7020.00	7020.00	240	\N	2026-07-06 18:40:38.402583	f
95	1	2026-04-27	HOTEL CATARATAS SA	9	\N	1	1	import_pdf	ARS	429249.80	429249.80	241	\N	2026-07-06 18:40:38.405483	f
96	1	2026-04-30	PEDIDOSYA*TEQUESUR	1	\N	1	1	import_pdf	ARS	14320.00	14320.00	242	\N	2026-07-06 18:40:38.408281	f
97	1	2026-04-30	FOOD PATAGONIA SA	9	\N	1	1	import_pdf	ARS	22000.00	22000.00	243	\N	2026-07-06 18:40:38.412006	f
98	1	2026-03-26	COMISION CTA PWORLD	3	\N	1	1	import_pdf	ARS	61157.02	61157.02	244	\N	2026-07-06 18:40:38.413998	t
99	1	2026-04-30	DB IVA $ 21% 61.157,02	4	\N	1	1	import_pdf	ARS	12842.97	12842.97	245	\N	2026-07-06 18:40:38.416926	f
100	1	2026-04-30	IIBB PERCEP-CABA 2,00%( 33368,17)	4	\N	1	1	import_pdf	ARS	667.36	667.36	246	\N	2026-07-06 18:40:38.420678	f
101	1	2026-04-30	IVA RG 4240 21%( 33368,17)	4	\N	1	1	import_pdf	ARS	7007.31	7007.31	247	\N	2026-07-06 18:40:38.423802	f
102	1	2026-04-30	DB.RG 5617 30% ( 20858,58 )	4	\N	1	1	import_pdf	ARS	6257.57	6257.57	248	\N	2026-07-06 18:40:38.426763	f
63	1	2026-04-02	MERPAGO*PARQUEGAS	2	14	1	1	import_pdf	ARS	447039.12	447039.12	209	TERMOTANQUE	2026-07-06 18:40:38.295491	f
73	1	2026-04-13	MERPAGO*TCTIENDAS	2	14	1	1	import_pdf	ARS	83930.00	83930.00	219	lamparitas led	2026-07-06 18:40:38.336042	f
103	1	2026-05-08	CR.RG 5617 30% M	4	\N	1	1	import_pdf	ARS	-6257.57	-6257.57	306	\N	2026-07-06 18:44:30.978277	f
104	1	2026-05-28	CR IVA $ 21 %	4	\N	1	1	import_pdf	ARS	-12095.80	-12095.80	307	\N	2026-07-06 18:44:30.982237	f
105	1	2026-05-28	MERPAGO*MERCADOLIBRE C.06/06	11	\N	1	1	import_pdf	ARS	9998.33	9998.33	308	\N	2026-07-06 18:44:30.985732	f
106	1	2026-05-28	MERPAGO*KAMADOARGENTI C.04/06	2	14	1	1	import_pdf	ARS	31083.50	31083.50	309	\N	2026-07-06 18:44:30.990435	f
107	1	2026-04-29	ACA PUERTO IGUAZU COMB	10	\N	1	1	import_pdf	ARS	35003.00	35003.00	310	\N	2026-07-06 18:44:30.994204	f
108	1	2026-04-30	HOTEL CATARATAS SA	9	\N	1	1	import_pdf	ARS	176000.00	176000.00	311	\N	2026-07-06 18:44:30.998376	f
109	1	2026-04-30	DLO*PEDIDOSYA PROPINA	1	\N	1	1	import_pdf	ARS	700.00	700.00	312	\N	2026-07-06 18:44:31.002739	f
110	1	2026-04-30	DLO*PEDIDOSYA PROPINA	1	\N	1	1	import_pdf	ARS	400.00	400.00	313	\N	2026-07-06 18:44:31.006303	f
111	1	2026-04-30	PEDIDOSYA*DIA ADROGUA I	1	\N	1	1	import_pdf	ARS	32134.00	32134.00	314	\N	2026-07-06 18:44:31.009334	f
112	1	2026-04-30	PEDIDOSYA*THOUSAND BURG	1	\N	1	1	import_pdf	ARS	39380.00	39380.00	315	\N	2026-07-06 18:44:31.012718	f
113	1	2026-04-30	PEDIDOSYA*DIA ADROGUA I	1	\N	1	1	import_pdf	ARS	-2300.00	-2300.00	316	\N	2026-07-06 18:44:31.016224	f
114	1	2026-05-02	PEDIDOSYA*CARREFOUR HIP	1	\N	1	1	import_pdf	ARS	32494.50	32494.50	317	\N	2026-07-06 18:44:31.019608	f
115	1	2026-05-02	PEDIDOSYA*EXTRA	1	\N	1	1	import_pdf	ARS	982.25	982.25	318	\N	2026-07-06 18:44:31.022755	f
116	1	2026-05-03	DLO*PEDIDOSYA PLUS	1	\N	1	1	import_pdf	ARS	5990.00	5990.00	319	\N	2026-07-06 18:44:31.026203	f
117	1	2026-05-07	MOVISTAR HOGAR 000000568729017	3	5	1	1	import_pdf	ARS	47759.99	47759.99	320	\N	2026-07-06 18:44:31.029	t
118	1	2026-05-08	DLO*PEDIDOSYA PROPINA	1	\N	1	1	import_pdf	ARS	400.00	400.00	321	\N	2026-07-06 18:44:31.032403	f
119	1	2026-05-08	PEDIDOSYA*THOUSAND BURG	1	\N	1	1	import_pdf	ARS	40790.00	40790.00	322	\N	2026-07-06 18:44:31.036011	f
120	1	2026-05-09	DLO*PEDIDOSYA PROPINA	1	\N	1	1	import_pdf	ARS	300.00	300.00	323	\N	2026-07-06 18:44:31.039653	f
121	1	2026-05-09	PEDIDOSYA*PERTUTTI ADRO	1	\N	1	1	import_pdf	ARS	38590.00	38590.00	324	\N	2026-07-06 18:44:31.042701	f
122	1	2026-05-10	PEDIDOSYA*THOUSAND BURG	1	\N	1	1	import_pdf	ARS	20730.00	20730.00	325	\N	2026-07-06 18:44:31.045885	f
123	1	2026-05-10	PEDIDOSYA*THOUSAND BURG	1	\N	1	1	import_pdf	ARS	-11165.00	-11165.00	326	\N	2026-07-06 18:44:31.04909	f
124	1	2026-05-12	OPENAI *CHATGPT SUBSCR	8	\N	1	1	import_pdf	USD	20.00	20000.00	327	\N	2026-07-06 18:44:31.053345	t
125	1	2026-05-28	MERPAGO*WALDENCASES C.01/03	11	\N	1	1	import_pdf	ARS	26250.00	26250.00	328	\N	2026-07-06 18:44:31.057595	f
126	1	2026-05-14	DISCO SM 037	2	\N	1	1	import_pdf	ARS	163472.90	163472.90	329	\N	2026-07-06 18:44:31.061654	f
127	1	2026-05-15	CLARO DEB AUT 000021326330519	3	5	1	1	import_pdf	ARS	27211.25	27211.25	330	\N	2026-07-06 18:44:31.064537	t
128	1	2026-05-18	METROGAS SA DEB 020307417400	3	3	1	1	import_pdf	ARS	41824.69	41824.69	331	\N	2026-07-06 18:44:31.067148	t
129	1	2026-05-18	AMAZON PRIME*TT9 f9vrF5l8d	8	\N	1	1	import_pdf	USD	14.99	14990.00	332	\N	2026-07-06 18:44:31.070376	t
130	1	2026-05-18	STEAMGAMES.COM 4 425952298	11	\N	1	1	import_pdf	USD	8.99	8990.00	333	\N	2026-07-06 18:44:31.073924	f
131	1	2026-05-19	CAJA SEG-PROMO BB023838068 -0	7	7	1	1	import_pdf	ARS	200621.00	200621.00	334	\N	2026-07-06 18:44:31.077106	t
132	1	2026-05-19	DLO*PEDIDOSYA PROPINA	1	\N	1	1	import_pdf	ARS	600.00	600.00	335	\N	2026-07-06 18:44:31.08051	f
133	1	2026-05-19	PEDIDOSYA*CUQUET HOUSE	1	\N	1	1	import_pdf	ARS	12530.00	12530.00	336	\N	2026-07-06 18:44:31.084008	f
134	1	2026-05-21	MERPAGO*LUVIKSA	2	10	1	1	import_pdf	ARS	128757.00	128757.00	337	\N	2026-07-06 18:44:31.087933	f
135	1	2026-05-23	PEDIDOSYA*CUQUET HOUSE	1	\N	1	1	import_pdf	ARS	14430.00	14430.00	338	\N	2026-07-06 18:44:31.091221	f
136	1	2026-05-24	PEDIDOSYA*DER GRUND TEM	1	\N	1	1	import_pdf	ARS	41390.00	41390.00	339	\N	2026-07-06 18:44:31.095194	f
137	1	2026-05-24	STEAMGAMES.COM 4259522985	11	33	1	1	import_pdf	USD	19.99	19990.00	340	\N	2026-07-06 18:44:31.098643	f
138	1	2026-05-25	DLO*PEDIDOSYA PROPINA	1	\N	1	1	import_pdf	ARS	800.00	800.00	341	\N	2026-07-06 18:44:31.102142	f
139	1	2026-05-26	PEDIDOSYA*GLORIOSO CHUR	1	\N	1	1	import_pdf	ARS	11630.00	11630.00	342	\N	2026-07-06 18:44:31.105216	f
140	1	2026-05-27	OSDE 000062938930501	6	\N	1	1	import_pdf	ARS	202741.53	202741.53	343	\N	2026-07-06 18:44:31.108298	f
141	1	2026-05-27	STEAMGAMES.COM 4259522985	11	33	1	1	import_pdf	USD	5.62	5620.00	344	\N	2026-07-06 18:44:31.112498	f
142	1	2026-04-30	COMISION CTA PWORLD	3	\N	1	1	import_pdf	ARS	57599.07	57599.07	345	\N	2026-07-06 18:44:31.115195	t
143	1	2026-05-28	DB IVA $ 21% 57.599,07	4	\N	1	1	import_pdf	ARS	12095.80	12095.80	346	\N	2026-07-06 18:44:31.11817	f
144	1	2026-05-28	IIBB PERCEP-CABA 2,00%( 33871,75)	4	\N	1	1	import_pdf	ARS	677.43	677.43	347	\N	2026-07-06 18:44:31.12176	f
145	1	2026-05-28	IIBB PERCEP-CABA 2,00%( 36174,12)	4	\N	1	1	import_pdf	ARS	723.48	723.48	348	\N	2026-07-06 18:44:31.125082	f
146	1	2026-05-28	IVA RG 4240 21%( 33871,75)	4	\N	1	1	import_pdf	ARS	7113.06	7113.06	349	\N	2026-07-06 18:44:31.12851	f
147	1	2026-05-28	IVA RG 4240 21%( 36174,12)	4	\N	1	1	import_pdf	ARS	7596.56	7596.56	350	\N	2026-07-06 18:44:31.131831	f
148	1	2026-05-28	DB.RG 5617 30% ( 49423,37 )	4	\N	1	1	import_pdf	ARS	14827.01	14827.01	351	\N	2026-07-06 18:44:31.135201	f
149	1	2026-05-28	DEV COMISION CTA PWORLD	3	\N	1	1	import_pdf	ARS	-57599.07	-57599.07	352	\N	2026-07-06 18:44:31.137916	t
150	1	2026-03-26	MERPAGO*MERCADOLIBRE C.04/06	11	\N	1	1	import_pdf	ARS	9998.33	9998.33	443	\N	2026-07-06 18:48:10.291078	f
151	1	2026-03-26	MERPAGO*KAMADOARGENTI C.02/03	2	14	1	1	import_pdf	ARS	14412.33	14412.33	444	\N	2026-07-06 18:48:10.295373	f
152	1	2026-03-26	MERPAGO*KAMADOARGENTI C.02/06	2	14	1	1	import_pdf	ARS	31083.50	31083.50	445	\N	2026-07-06 18:48:10.300784	f
153	1	2026-03-26	MERPAGO*SOHODENIMROPA C.02/03	14	\N	1	1	import_pdf	ARS	40186.66	40186.66	446	\N	2026-07-06 18:48:10.304879	f
154	1	2026-03-26	MERPAGO*ACIUM C.02/03	13	\N	1	1	import_pdf	ARS	69333.33	69333.33	447	\N	2026-07-06 18:48:10.308975	f
155	1	2026-03-01	MERPAGO*TADA	2	22	1	1	import_pdf	ARS	42000.00	42000.00	448	\N	2026-07-06 18:48:10.314694	f
156	1	2026-03-01	PEDIDOSYA*HARRYS KILLER	1	\N	1	1	import_pdf	ARS	30560.00	30560.00	449	\N	2026-07-06 18:48:10.318974	f
157	1	2026-03-02	PEDIDOSYA*TEQUESUR	1	\N	1	1	import_pdf	ARS	14300.00	14300.00	450	\N	2026-07-06 18:48:10.322838	f
158	1	2026-03-03	DLO*PEDIDOSYA PLUS	1	\N	1	1	import_pdf	ARS	5990.00	5990.00	451	\N	2026-07-06 18:48:10.326679	f
159	1	2026-03-06	DLO*PEDIDOSYA PROPINA	1	\N	1	1	import_pdf	ARS	300.00	300.00	452	\N	2026-07-06 18:48:10.330036	f
160	1	2026-03-06	PEDIDOSYA*FABRIC SUSHI	1	\N	1	1	import_pdf	ARS	66158.00	66158.00	453	\N	2026-07-06 18:48:10.333407	f
161	1	2026-03-09	MERPAGO*CMORRES	2	20	1	1	import_pdf	ARS	67800.00	67800.00	454	\N	2026-07-06 18:48:10.336679	f
162	1	2026-03-10	MOVISTAR HOGAR 000000568729017	3	5	1	1	import_pdf	ARS	44860.00	44860.00	455	\N	2026-07-06 18:48:10.339839	t
163	1	2026-03-11	MERPAGO*DOGCENTER	17	27	1	1	import_pdf	ARS	64222.00	64222.00	456	\N	2026-07-06 18:48:10.344491	f
164	1	2026-03-13	PEDIDOSYA*HARRYS KILLER	1	\N	1	1	import_pdf	ARS	33070.00	33070.00	457	\N	2026-07-06 18:48:10.348466	f
165	1	2026-03-14	DLO*PEDIDOSYA PROPINA	1	\N	1	1	import_pdf	ARS	700.00	700.00	458	\N	2026-07-06 18:48:10.352035	f
166	1	2026-03-14	PEDIDOSYA*JIRO SUSHI AD	1	\N	1	1	import_pdf	ARS	72982.00	72982.00	459	\N	2026-07-06 18:48:10.355506	f
167	1	2026-03-15	CLARO DEB AUT 000021326330519	3	5	1	1	import_pdf	ARS	25066.26	25066.26	460	\N	2026-07-06 18:48:10.357994	t
168	1	2026-03-16	EDESUR	3	1	1	1	import_pdf	ARS	127135.77	127135.77	461	\N	2026-07-06 18:48:10.360821	t
169	1	2026-03-17	CAJA SEG-PROMO BB023838068 -0	7	7	1	1	import_pdf	ARS	196226.00	196226.00	462	\N	2026-07-06 18:48:10.363621	t
170	1	2026-03-17	PEDIDOSYA*PERTUTTI ADRO	1	\N	1	1	import_pdf	ARS	38570.00	38570.00	463	\N	2026-07-06 18:48:10.367183	f
171	1	2026-03-17	AMAZON PRIME*BJ8 1iWVOeHn2	8	\N	1	1	import_pdf	USD	14.99	14990.00	464	\N	2026-07-06 18:48:10.37171	t
172	1	2026-03-18	MERPAGO*MERCADOLIBRE	11	\N	1	1	import_pdf	ARS	126074.80	126074.80	465	\N	2026-07-06 18:48:10.374784	f
173	1	2026-03-19	PEDIDOSYA*PERTUTTI ADRO	1	\N	1	1	import_pdf	ARS	23470.00	23470.00	466	\N	2026-07-06 18:48:10.379149	f
174	1	2026-03-20	CABIFY2612UYZHOPPT	10	\N	1	1	import_pdf	ARS	23294.19	23294.19	467	\N	2026-07-06 18:48:10.384512	f
175	1	2026-03-20	OSDE 000062938930501	6	\N	1	1	import_pdf	ARS	188780.44	188780.44	468	\N	2026-07-06 18:48:10.388098	f
176	1	2026-03-20	BONIF. CONSUMO CABIFY2612UYZHOPPT	11	34	1	1	import_pdf	ARS	-4001.94	-4001.94	469	\N	2026-07-06 18:48:10.392535	f
177	1	2026-03-21	MERPAGO*CMORRES	2	20	1	1	import_pdf	ARS	95088.60	95088.60	470	\N	2026-07-06 18:48:10.395809	f
178	1	2026-03-21	VICTORIA BROWN	11	34	1	1	import_pdf	ARS	166000.00	166000.00	471	\N	2026-07-06 18:48:10.400135	f
179	1	2026-03-21	PAYU*AR*UBER	11	34	1	1	import_pdf	ARS	19615.00	19615.00	472	\N	2026-07-06 18:48:10.404524	f
180	1	2026-03-25	METROGAS SA DEB 020307417400	3	3	1	1	import_pdf	ARS	37275.45	37275.45	473	\N	2026-07-06 18:48:10.407333	t
181	1	2026-02-26	COMISION CTA PWORLD	3	\N	1	1	import_pdf	ARS	61157.02	61157.02	474	\N	2026-07-06 18:48:10.410506	f
182	1	2026-03-26	DB IVA $ 21% 61.157,02	4	\N	1	1	import_pdf	ARS	12842.97	12842.97	475	\N	2026-07-06 18:48:10.413984	f
183	1	2026-03-26	IIBB PERCEP-CABA 2,00%( 20648,72)	4	\N	1	1	import_pdf	ARS	412.97	412.97	476	\N	2026-07-06 18:48:10.41793	f
184	1	2026-03-26	IVA RG 4240 21%( 20648,72)	4	\N	1	1	import_pdf	ARS	4336.23	4336.23	477	\N	2026-07-06 18:48:10.421297	f
185	1	2026-03-26	DB.RG 5617 30% ( 20648,72 )	4	\N	1	1	import_pdf	ARS	6194.61	6194.61	478	\N	2026-07-06 18:48:10.424889	f
186	1	2026-07-02	PAGO DE SERVICIOS TARJETA 18073039 OP3802	3	\N	1	1	bank_import	ARS	-38579.44	-38579.44	568	\N	2026-07-06 19:15:56.523915	t
187	1	2026-07-02	TRANSFERENCIA	2	24	1	1	bank_import	ARS	-119500.00	-119500.00	569	\N	2026-07-06 19:15:56.529568	f
188	1	2026-07-01	TRANSFERENCIA	13	\N	1	1	bank_import	ARS	-210162.00	-210162.00	570	\N	2026-07-06 19:15:56.535507	f
189	1	2026-06-30	PAGO DE SERVICIOS TARJETA 18073039 OP9422	3	\N	1	1	bank_import	ARS	-38362.49	-38362.49	572	\N	2026-07-06 19:15:56.545666	t
190	1	2026-06-30	PAGO DE SERVICIOS TARJETA 18073039 OP2788	3	\N	1	1	bank_import	ARS	-37827.74	-37827.74	573	\N	2026-07-06 19:15:56.549683	t
191	1	2026-06-30	PAGO DE SERVICIOS TARJETA 18073039 OP5446	3	\N	1	1	bank_import	ARS	-16580.10	-16580.10	574	\N	2026-07-06 19:15:56.553376	t
192	1	2026-06-30	TRANSFERENCIA	13	\N	1	1	bank_import	ARS	-60000.00	-60000.00	575	\N	2026-07-06 19:15:56.560433	f
193	1	2026-06-18	TRANSFERENCIA	13	\N	1	1	bank_import	ARS	-50000.00	-50000.00	577	\N	2026-07-06 19:15:56.570878	f
194	1	2026-06-11	TRANSFERENCIA CCP316 316621 5 Nro:00010008	13	\N	1	1	bank_import	ARS	-50000.00	-50000.00	582	\N	2026-07-06 19:15:56.578332	f
195	1	2026-06-05	PAGO CON VISA DEBITO 18073039 OP4102	3	1	1	1	bank_import	ARS	-349850.36	-349850.36	584	\N	2026-07-06 19:15:56.583136	t
196	1	2026-06-05	PAGO DE SERVICIOS TARJETA 18073039 OP8518	3	\N	1	1	bank_import	ARS	-36539.04	-36539.04	585	\N	2026-07-06 19:15:56.586601	t
197	1	2026-06-05	PAGO DE SERVICIOS TARJETA 18073039 OP8363	3	\N	1	1	bank_import	ARS	-16187.00	-16187.00	586	\N	2026-07-06 19:15:56.59006	t
198	1	2026-05-21	TRANSFERENCIA CAP027 027024 8 Nro:00010008	13	\N	1	1	bank_import	ARS	-130000.00	-130000.00	594	\N	2026-07-06 19:15:56.605324	f
199	1	2026-05-19	TRANSFERENCIA	2	22	1	1	bank_import	ARS	-446976.00	-446976.00	595	\N	2026-07-06 19:15:56.611716	f
200	1	2026-05-19	TRANSFERENCIA	13	\N	1	1	bank_import	ARS	-50000.00	-50000.00	596	\N	2026-07-06 19:15:56.617089	f
201	1	2026-05-05	TRANSFERENCIA CAP027 027024 8 Nro:00010008	11	\N	1	1	bank_import	ARS	-1000000.00	-1000000.00	599	\N	2026-07-06 19:15:56.626426	f
202	1	2026-04-27	Transferencia inmediata	13	\N	1	1	bank_import	ARS	-100000.00	-100000.00	603	\N	2026-07-06 19:15:56.634008	f
203	1	2026-04-27	PAGO DE SERVICIOS TARJETA 18073039 OP1619	3	\N	1	1	bank_import	ARS	-36539.04	-36539.04	604	\N	2026-07-06 19:15:56.637414	t
204	1	2026-04-27	PAGO DE SERVICIOS TARJETA 18073039 OP5935	3	\N	1	1	bank_import	ARS	-15703.10	-15703.10	605	\N	2026-07-06 19:15:56.640387	t
205	1	2026-04-24	TRANSFERENCIA	13	\N	1	1	bank_import	ARS	-30000.00	-30000.00	608	\N	2026-07-06 19:15:56.654568	f
206	1	2026-04-21	Transferencia inmediata	13	\N	1	1	bank_import	ARS	-1370000.00	-1370000.00	609	\N	2026-07-06 19:15:56.659584	f
207	1	2026-04-20	DEBITO DIRECTO	4	\N	1	1	bank_import	ARS	-194300.32	-194300.32	612	\N	2026-07-06 19:15:56.663592	f
208	1	2026-04-13	TRANSFERENCIA	3	\N	1	1	bank_import	ARS	-100000.00	-100000.00	613	\N	2026-07-06 19:15:56.668873	t
209	1	2026-04-13	Transferencia inmediata	13	\N	1	1	bank_import	ARS	-214300.00	-214300.00	614	\N	2026-07-06 19:15:56.674603	f
210	1	2026-04-08	PAGO DE SERVICIOS TARJETA 18073039 OP8708	3	\N	1	1	bank_import	ARS	-35946.61	-35946.61	616	\N	2026-07-06 19:15:56.677145	t
211	1	2026-04-08	PAGO DE SERVICIOS TARJETA 18073039 OP3682	3	\N	1	1	bank_import	ARS	-33132.40	-33132.40	617	\N	2026-07-06 19:15:56.679921	t
212	1	2026-04-08	PAGO DE SERVICIOS TARJETA 18073039 OP7422	3	\N	1	1	bank_import	ARS	-32332.42	-32332.42	618	\N	2026-07-06 19:15:56.683567	t
213	1	2026-04-08	PAGO DE SERVICIOS TARJETA 18073039 OP9027	3	\N	1	1	bank_import	ARS	-15331.30	-15331.30	619	\N	2026-07-06 19:15:56.686986	t
214	1	2026-04-06	Transferencia inmediata	13	\N	1	1	bank_import	ARS	-200000.00	-200000.00	623	\N	2026-07-06 19:15:56.693135	f
215	1	2026-03-25	TRANSFERENCIA	2	\N	1	1	bank_import	ARS	-328354.00	-328354.00	627	\N	2026-07-06 19:15:56.707227	f
216	1	2026-03-20	DEBITO DIRECTO	4	\N	1	1	bank_import	ARS	-194300.32	-194300.32	630	\N	2026-07-06 19:15:56.721131	f
217	1	2026-03-10	PAGO DE SERVICIOS TARJETA 18073039 OP3266	3	\N	1	1	bank_import	ARS	-32332.42	-32332.42	632	\N	2026-07-06 19:15:56.728333	t
218	1	2026-03-10	PAGO DE SERVICIOS TARJETA 18073039 OP1997	3	\N	1	1	bank_import	ARS	-31814.94	-31814.94	633	\N	2026-07-06 19:15:56.731161	t
219	1	2026-03-10	PAGO DE SERVICIOS TARJETA 18073039 OP3086	3	\N	1	1	bank_import	ARS	-14938.20	-14938.20	634	\N	2026-07-06 19:15:56.734533	t
220	1	2026-03-05	TRANSFERENCIA	13	\N	1	1	bank_import	ARS	-200000.00	-200000.00	635	\N	2026-07-06 19:15:56.740537	f
221	1	2026-02-20	DEBITO DIRECTO	4	\N	1	1	bank_import	ARS	-194300.32	-194300.32	642	\N	2026-07-06 19:15:56.74929	f
222	1	2026-02-18	TRANSFERENCIA	13	\N	1	1	bank_import	ARS	-150000.00	-150000.00	646	\N	2026-07-06 19:15:56.758286	f
223	1	2026-02-11	PAGO DE SERVICIOS TARJETA 18073039 OP6471	3	\N	1	1	bank_import	ARS	-32979.07	-32979.07	649	\N	2026-07-06 19:15:56.767408	t
224	1	2026-02-11	PAGO DE SERVICIOS TARJETA 18073039 OP1526	3	\N	1	1	bank_import	ARS	-31427.40	-31427.40	650	\N	2026-07-06 19:15:56.770601	t
225	1	2026-02-11	PAGO DE SERVICIOS TARJETA 18073039 OP3417	3	\N	1	1	bank_import	ARS	-30591.26	-30591.26	651	\N	2026-07-06 19:15:56.774102	t
226	1	2026-02-10	Transferencia inmediata	13	\N	1	1	bank_import	ARS	-194300.32	-194300.32	652	\N	2026-07-06 19:15:56.780752	f
227	1	2026-02-04	TRANSFERENCIA	13	\N	1	1	bank_import	ARS	-60000.00	-60000.00	653	\N	2026-07-06 19:15:56.785915	f
\.


--
-- Data for Name: fx_rates; Type: TABLE DATA; Schema: public; Owner: spent
--

COPY public.fx_rates (id, date, source, from_currency, to_currency, rate) FROM stdin;
1	2026-05-01	blue_average	USD	ARS	1000.0000
\.


--
-- Data for Name: home_groups; Type: TABLE DATA; Schema: public; Owner: spent
--

COPY public.home_groups (id, name, created_at) FROM stdin;
1	Casa Adrogue	2026-07-06 00:36:45.969723
\.


--
-- Data for Name: import_batches; Type: TABLE DATA; Schema: public; Owner: spent
--

COPY public.import_batches (id, home_group_id, uploaded_by_user_id, filename, source_type, statement_account, period_label, status, created_at) FROM stdin;
5	1	1	Resumen (4).pdf	bbva_visa_pdf	0838433696	29-Ene-26	committed	2026-07-06 17:56:39.772166
4	1	1	Resumen (3).pdf	bbva_visa_pdf	0838433696	26-Feb-26	committed	2026-07-06 17:56:37.044664
6	1	1	Resumen (1).pdf	bbva_visa_pdf	0838433696	30-Abr-26	committed	2026-07-06 18:34:06.935447
8	1	1	Resumen.pdf	bbva_visa_pdf	0838433696	28-May-26	committed	2026-07-06 18:42:29.066771
11	1	1	Resumen (2).pdf	bbva_visa_pdf	0838433696	26-Mar-26	committed	2026-07-06 18:46:47.228833
14	1	1	Detalle_mov_cuenta_06_07_2026.xls	bbva_account_xls	Detalle de Movimientos de Cuenta: CA$ 316-423808/7	2026-02-04 a 2026-07-02	parsed	2026-07-06 18:54:51.15715
\.


--
-- Data for Name: import_lines; Type: TABLE DATA; Schema: public; Owner: spent
--

COPY public.import_lines (id, import_batch_id, home_group_id, date, description, coupon, kind, currency, original_amount, suggested_category_id, suggested_subcategory_id, status, fingerprint, raw_text, suggested_recurring) FROM stdin;
202	6	1	2026-04-30	MERPAGO*SOHODENIMROPA C.03/03	786986	payment	ARS	40186.66	\N	\N	committed	6:4acb7a47188db30ab99d40b50a96674c408ca08fa6d87bcc55c8e7426d633429	16-Feb-26 MERPAGO*SOHODENIMROPA C.03/03 786986 40.186,66	f
203	6	1	2026-04-30	MERPAGO*ACIUM C.03/03	513339	payment	ARS	69333.33	\N	\N	committed	6:a87a1011344694f6d380554fa318a3e73ba8ee7f1952afda046b53fdb478ba23	21-Feb-26 MERPAGO*ACIUM C.03/03 513339 69.333,33	f
204	6	1	2026-03-29	DLO*PEDIDOSYA PROPINA	004791	purchase	ARS	200.00	1	\N	committed	6:81cc53af776d7187cc7220c6d1c51426a9a121120944483ac21629148a89cdfb	29-Mar-26 DLO*PEDIDOSYA PROPINA 004791 200,00	f
205	6	1	2026-03-29	PEDIDOSYA*TEQUESUR	005439	purchase	ARS	14310.00	1	\N	committed	6:faad905848e395575f37302cd222861a1c718e5032ba88f58ecfcec164472e24	29-Mar-26 PEDIDOSYA*TEQUESUR 005439 14.310,00	f
206	6	1	2026-03-29	PEDIDOSYA*KFC ADROGUE	005384	purchase	ARS	17410.00	1	\N	committed	6:aa6f2da8f26c463e02a4eeed11579946012aae3392cc9c03a0083cecaef0e1ca	29-Mar-26 PEDIDOSYA*KFC ADROGUE 005384 17.410,00	f
207	6	1	2026-03-31	MERPAGO*PELONLINE	672779	payment	ARS	38340.00	\N	\N	committed	6:a6495324d6016d340c8c612c339c71ce2f1021728e55cd6af438068316330315	31-Mar-26 MERPAGO*PELONLINE 672779 38.340,00	f
208	6	1	2026-03-31	MERPAGO*MERCADOLIBRE	568628	payment	ARS	40948.99	11	\N	committed	6:a424e5809a0c4648b94a33dd022159eb23cc6289453c53c9baba2799915b5a7d	31-Mar-26 MERPAGO*MERCADOLIBRE 568628 40.948,99	f
209	6	1	2026-04-02	MERPAGO*PARQUEGAS	022601	payment	ARS	447039.12	\N	\N	committed	6:9a9b770cb3abc015403c3b2f662ba666e4167810c37c7625820760efe7058138	02-Abr-26 MERPAGO*PARQUEGAS 022601 447.039,12	f
210	6	1	2026-04-03	DLO*PEDIDOSYA PLUS	002145	purchase	ARS	5990.00	1	\N	committed	6:b8cdaf14cb2147d474be333a9f76cbb86c36b9810bf3c3608ad5793709e64743	03-Abr-26 DLO*PEDIDOSYA PLUS 002145 5.990,00	f
211	6	1	2026-04-04	MERPAGO*CMORRES	168981	payment	ARS	71279.40	\N	\N	committed	6:66c1176e78e7c49925e00c64d30cb9b83dd90d97d7f42badce16a65909ee5840	04-Abr-26 MERPAGO*CMORRES 168981 71.279,40	f
212	6	1	2026-04-05	DISCO SM 037 MODO	006066	purchase	ARS	164600.18	2	\N	committed	6:477830ef9c7b829919a2cce4313dbce42caf14d1eec0ca52a30ea34826bc7ef6	05-Abr-26 DISCO SM 037 MODO 006066 164.600,18	f
213	6	1	2026-04-09	MOVISTAR HOGAR 000000568729017	000001	purchase	ARS	46307.98	3	5	committed	6:1286697087ad5724b71c8be991734db50ec31a08eacce635e022506537efa687	09-Abr-26 MOVISTAR HOGAR 000000568729017 000001 46.307,98	t
214	6	1	2026-04-09	WL *Steam Purchase	568983	purchase	USD	20.09	11	\N	committed	6:7d466309b2ffeaa4fcf9c125ee907b1d859ae6e90435d2899e57665c0a5fbe17	09-Abr-26 WL *Steam Purchase USD 20,09 568983 20,09	f
215	6	1	2026-04-10	MERPAGO*CMORRES	938089	payment	ARS	99034.18	2	20	committed	6:6e398f206a51fe923734c2461c88f772e80876d3dff366438aab032a9cb02524	10-Abr-26 MERPAGO*CMORRES 938089 99.034,18	f
216	6	1	2026-04-11	DIA TIENDA 5556	329267	purchase	ARS	3785.00	\N	\N	committed	6:aeb797ed200166150ae50e2e2f5fa55d19e073792bf539a6a2de6d6c25aaeaf7	11-Abr-26 DIA TIENDA 5556 329267 3.785,00	f
217	6	1	2026-04-12	Crunchyroll LLC	409132	purchase	ARS	7379.79	\N	\N	committed	6:79e09ed4c217543bf819fe0cc509341cc5583aba0b20d9fa66e946c2dd088d0f	12-Abr-26 Crunchyroll LLC 409132 7.379,79	f
218	6	1	2026-04-12	PEDIDOSYA*DER GRUND TEM	007316	purchase	ARS	42480.00	1	\N	committed	6:b68b4c94819860748721a97449114ed4c47b0a323171cd5c25452629afac73f9	12-Abr-26 PEDIDOSYA*DER GRUND TEM 007316 42.480,00	f
219	6	1	2026-04-13	MERPAGO*TCTIENDAS	356293	payment	ARS	83930.00	\N	\N	committed	6:580c2eba4ba5b164e7f4180f06033c548a28b84c85bf3821210910fed6c7f974	13-Abr-26 MERPAGO*TCTIENDAS 356293 83.930,00	f
220	6	1	2026-04-13	SHELL	004410	purchase	ARS	117000.00	\N	\N	committed	6:88013a73d1e98eaddf09fc8bec75fd08bf5b93baf010209f78b06628b975e4d8	13-Abr-26 SHELL 004410 117.000,00	f
221	6	1	2026-04-15	WL *Steam Purchase	801745	purchase	USD	11.99	11	\N	committed	6:a490353a18db851efbdb807a0213f2ad81ab5a67cf9bdc7e2b3ae04631bdc649	15-Abr-26 WL *Steam Purchase USD 11,99 801745 11,99	f
222	6	1	2026-04-16	MERPAGO*CMORRES	878663	payment	ARS	52227.35	2	20	committed	6:1abec98d05d971658c1f9c3a0f60243264e466c272dfb3591be595c15484d9ce	16-Abr-26 MERPAGO*CMORRES 878663 52.227,35	f
231	6	1	2026-04-21	DLO*PEDIDOSYA PROPINA	007408	purchase	ARS	300.00	1	\N	committed	6:f013c132153b8ffe2491ec793ba12d497c9dec92abf389b06c877d9e40272850	21-Abr-26 DLO*PEDIDOSYA PROPINA 007408 300,00	f
232	6	1	2026-04-21	PEDIDOSYA*CUQUET HOUSE	008676	purchase	ARS	13420.00	1	\N	committed	6:a08357500ecc28a85130d33248f7439eb9b40eed636669ecd9e643c74663b5d3	21-Abr-26 PEDIDOSYA*CUQUET HOUSE 008676 13.420,00	f
233	6	1	2026-04-23	DLO*PEDIDOSYA PROPINA	001821	purchase	ARS	650.00	1	\N	committed	6:02400705f84428905ac7bf0910e4860f022eeef5d913af20288a8d52425e5c45	23-Abr-26 DLO*PEDIDOSYA PROPINA 001821 650,00	f
234	6	1	2026-04-23	PEDIDOSYA*THOUSAND BURG	008961	purchase	ARS	20720.00	1	\N	committed	6:f1e892a54f0c6b917dc90905115fa674f45d9d5433348f464d30c2e6581e12b8	23-Abr-26 PEDIDOSYA*THOUSAND BURG 008961 20.720,00	f
235	6	1	2026-04-25	STARBUCKS PORTAL LOMAS	009398	purchase	ARS	43200.00	\N	\N	committed	6:eab00ad64533419111e9e1a3ac4aa149dc9a109ae4e433a8ac069622a60ed49e	25-Abr-26 STARBUCKS PORTAL LOMAS 009398 43.200,00	f
236	6	1	2026-04-25	OSDE 000062938930501	007486	purchase	ARS	195211.21	6	\N	committed	6:42235e467d6a06a9fdae772a3cfba30fda164e65567d2a52d9431da98f65d09b	25-Abr-26 OSDE 000062938930501 007486 195.211,21	f
237	6	1	2026-04-26	EDESUR	006406	purchase	ARS	100895.35	3	1	committed	6:940b6e41f62550cddb5410ce41c07ae2e0dd1d9b45a9d509a6f447e124e3f6bb	26-Abr-26 EDESUR 006406 100.895,35	t
238	6	1	2026-04-26	DLO*PEDIDOSYA PROPINA	002252	purchase	ARS	400.00	1	\N	committed	6:c020bda5ac316aabe264d8e11e9883fe788950d928b3831dee2eba3f858de12d	26-Abr-26 DLO*PEDIDOSYA PROPINA 002252 400,00	f
239	6	1	2026-04-26	PEDIDOSYA*PERTUTTI ADRO	009534	purchase	ARS	46580.00	1	\N	committed	6:51d2ab41f59334cf51f67a03c2f326e0d9f8efc4a5f3e64f0b10493f77da7b24	26-Abr-26 PEDIDOSYA*PERTUTTI ADRO 009534 46.580,00	f
240	6	1	2026-04-26	PEDIDOSYA*LAS MEDIALUNA	009470	purchase	ARS	7020.00	1	\N	committed	6:9d48354ff380d7161f953237a046b3d72510ba5b1f35b792964cc8cf0e9d9cf6	26-Abr-26 PEDIDOSYA*LAS MEDIALUNA 009470 7.020,00	f
241	6	1	2026-04-27	HOTEL CATARATAS SA	013772	purchase	ARS	429249.80	9	\N	committed	6:ee9b9f53dfa153b99a20fa9d7d5aa563ab2d007b2e7ad314856890d8c9aee69b	27-Abr-26 HOTEL CATARATAS SA 013772 429.249,80	f
306	8	1	2026-05-08	CR.RG 5617 30% M	\N	tax	ARS	-6257.57	4	\N	committed	8:bb57f7f799f0ffb86346dcc4af90c94757ee5a201baa1914dc1e7c625c3177ac	08-May-26 CR.RG 5617 30% M -6.257,57 3-91300005-03 .orN TIUC otpircsnI elbasnopseR AVI - .A.S anitnegrA AVBB ocnaB	f
308	8	1	2026-05-28	MERPAGO*MERCADOLIBRE C.06/06	821025	payment	ARS	9998.33	11	\N	committed	8:d47985bcd70a6d71210427544c4e8c0215ac729138b16251c4e49c4f53a6924c	03-Dic-25 MERPAGO*MERCADOLIBRE C.06/06 821025 9.998,33	f
309	8	1	2026-05-28	MERPAGO*KAMADOARGENTI C.04/06	260104	payment	ARS	31083.50	2	14	committed	8:9d5a0d6d4524daeeb0a19c48a999baaff6c7c53ce2afc2aebf3d4031c5717a0a	04-Feb-26 MERPAGO*KAMADOARGENTI C.04/06 260104 31.083,50	f
242	6	1	2026-04-30	PEDIDOSYA*TEQUESUR	009907	purchase	ARS	14320.00	1	\N	committed	6:eeca31722fe7236c47c0197744a6f4a81fdccda365e715dcec6f5ad13a8b5267	30-Abr-26 PEDIDOSYA*TEQUESUR 009907 14.320,00	f
243	6	1	2026-04-30	FOOD PATAGONIA SA	002041	purchase	ARS	22000.00	\N	\N	committed	6:194e1deef9c74fc7a064bc284d23e2b34948e7cf3185c264876a4c1ac9c51c59	30-Abr-26 FOOD PATAGONIA SA 002041 22.000,00 (cid:204)(cid:103)(cid:173)(cid:147)(cid:170)(cid:111)(cid:106)(cid:105)(cid:203) 3-91300005-03 .orN TIUC otpircsnI elbasnopseR AVI - .A.S anitnegrA AVBB ocnaB Impuestos, cargos e intereses	f
244	6	1	2026-03-26	COMISION CTA PWORLD	\N	fee	ARS	61157.02	3	\N	committed	6:e05e5d16f3c1ebf1c7384ccb3b58e26260800b31c754f049941e61cc40ab99ab	26-Mar-26 COMISION CTA PWORLD 61.157,02	t
245	6	1	2026-04-30	DB IVA $ 21% 61.157,02	\N	tax	ARS	12842.97	4	\N	committed	6:6438684da6e622ee370054a4ea60d7d695e229d490161849183bcb4506bc0f59	30-Abr-26 DB IVA $ 21% 61.157,02 12.842,97	f
246	6	1	2026-04-30	IIBB PERCEP-CABA 2,00%( 33368,17)	\N	tax	ARS	667.36	4	\N	committed	6:2651747500135bcda3de4a4b6caf9b8909bd8000ae87bab04df5aa28c32883dc	30-Abr-26 IIBB PERCEP-CABA 2,00%( 33368,17) 667,36	f
247	6	1	2026-04-30	IVA RG 4240 21%( 33368,17)	\N	tax	ARS	7007.31	4	\N	committed	6:3583ec450819c7f4c5b230a73350c35348b04d26321ac5ecf4cf85798ead6351	30-Abr-26 IVA RG 4240 21%( 33368,17) 7.007,31	f
194	6	1	2026-04-08	SU PAGO EN PESOS	\N	previous_payment	ARS	-1755494.52	\N	\N	ignored	6:ed12f82f49b492f5f6c4b1fbcf822e5ccadb50f6675cc9433f5956ee6791c6fd	08-Abr-26 SU PAGO EN PESOS -1.755.494,52	f
195	6	1	2026-04-08	SU PAGO EN USD	\N	previous_payment	USD	-14.99	\N	\N	ignored	6:df33021713e95c405bec99c572cc236f98029627e3df9e8f29a6867980a46e8a	08-Abr-26 SU PAGO EN USD -14,99	f
248	6	1	2026-04-30	DB.RG 5617 30% ( 20858,58 )	\N	tax	ARS	6257.57	4	\N	committed	6:70e0c961a2a314faf6d1b1ef33dfa7aefa2e0ae4067453c4b15eaf1959e93c08	30-Abr-26 DB.RG 5617 30% ( 20858,58 ) 6.257,57	f
310	8	1	2026-04-29	ACA PUERTO IGUAZU COMB	010421	purchase	ARS	35003.00	10	\N	committed	8:770dc5ce2342dca908d73ded157dc153caa4f82af9f501d1e337d0b3b824ef72	29-Abr-26 ACA PUERTO IGUAZU COMB 010421 35.003,00	f
311	8	1	2026-04-30	HOTEL CATARATAS SA	016760	purchase	ARS	176000.00	9	\N	committed	8:114aaf749c1be5772a636bfaf70637bf8b84df5dd4f46548cf7805d3194fc82c	30-Abr-26 HOTEL CATARATAS SA 016760 176.000,00	f
312	8	1	2026-04-30	DLO*PEDIDOSYA PROPINA	005069	purchase	ARS	700.00	1	\N	committed	8:ff15f18b40a279aafe2f78c047871fbca94a93ca98768b8441d31b91804ec0f9	30-Abr-26 DLO*PEDIDOSYA PROPINA 005069 700,00	f
313	8	1	2026-04-30	DLO*PEDIDOSYA PROPINA	005341	purchase	ARS	400.00	1	\N	committed	8:07962aa6ac02ea0f664e4457e164a2856709598561903470e0f35457dfa1cd70	30-Abr-26 DLO*PEDIDOSYA PROPINA 005341 400,00	f
314	8	1	2026-04-30	PEDIDOSYA*DIA ADROGUA I	009996	purchase	ARS	32134.00	1	\N	committed	8:9947db8b9c7bec4e758855e6de4ee865e9ce33ee7feb086eb11a10b3eda42b53	30-Abr-26 PEDIDOSYA*DIA ADROGUA I 009996 32.134,00	f
315	8	1	2026-04-30	PEDIDOSYA*THOUSAND BURG	000125	purchase	ARS	39380.00	1	\N	committed	8:7c95eb8d5531c01dc0ef6bf991da92418ebdc7f93034cde70289833b8728d029	30-Abr-26 PEDIDOSYA*THOUSAND BURG 000125 39.380,00	f
316	8	1	2026-04-30	PEDIDOSYA*DIA ADROGUA I	000001	refund	ARS	-2300.00	1	\N	committed	8:bcc518205d04965dcf1cae6e6c08fb291ac9b8463ca254a7bf05da7a8f9bfc11	30-Abr-26 PEDIDOSYA*DIA ADROGUA I 000001 -2.300,00	f
317	8	1	2026-05-02	PEDIDOSYA*CARREFOUR HIP	000434	purchase	ARS	32494.50	1	\N	committed	8:b1ed1da7b5367cbe5d0e11346d3c174dfceb001a7e6c0bd71332641b785bbe84	02-May-26 PEDIDOSYA*CARREFOUR HIP 000434 32.494,50	f
318	8	1	2026-05-02	PEDIDOSYA*EXTRA	004527	purchase	ARS	982.25	1	\N	committed	8:c9c0da579f06f4c52a4fe325da2775269577e590f4066cadb738d45399486edb	02-May-26 PEDIDOSYA*EXTRA 004527 982,25	f
319	8	1	2026-05-03	DLO*PEDIDOSYA PLUS	008016	purchase	ARS	5990.00	1	\N	committed	8:056ee4f2ea90a70bac03264510d448900cb3e5c72f524b6d9262f0704cca6b3c	03-May-26 DLO*PEDIDOSYA PLUS 008016 5.990,00	f
320	8	1	2026-05-07	MOVISTAR HOGAR 000000568729017	000001	purchase	ARS	47759.99	3	5	committed	8:1274acade3c1d846265e207eeedbaa5058018e84612a9eab42ed3a33d591cdc0	07-May-26 MOVISTAR HOGAR 000000568729017 000001 47.759,99	t
321	8	1	2026-05-08	DLO*PEDIDOSYA PROPINA	001386	purchase	ARS	400.00	1	\N	committed	8:29e138eec947464de3853aba29aa8fba18aeac2b3acdf1b7d9ec48f65581dbeb	08-May-26 DLO*PEDIDOSYA PROPINA 001386 400,00	f
322	8	1	2026-05-08	PEDIDOSYA*THOUSAND BURG	001425	purchase	ARS	40790.00	1	\N	committed	8:eb588501e99dd092b57c008da21e66291e47ea487484aa4cbfcd4563f4974f2b	08-May-26 PEDIDOSYA*THOUSAND BURG 001425 40.790,00	f
323	8	1	2026-05-09	DLO*PEDIDOSYA PROPINA	009131	purchase	ARS	300.00	1	\N	committed	8:a2b9669bd7836307811984e1b1e80f4ebe4d62e960027670528217ccfabff4ab	09-May-26 DLO*PEDIDOSYA PROPINA 009131 300,00	f
324	8	1	2026-05-09	PEDIDOSYA*PERTUTTI ADRO	001615	purchase	ARS	38590.00	1	\N	committed	8:24bf632656c4fa333102ea1c236d31b56f9b21f68477d2ead1a1cd56380cfa59	09-May-26 PEDIDOSYA*PERTUTTI ADRO 001615 38.590,00	f
325	8	1	2026-05-10	PEDIDOSYA*THOUSAND BURG	001818	purchase	ARS	20730.00	1	\N	committed	8:fe5346de8a6eec9f1debe180452907f39761992e896277b2f0d74be431e2b69a	10-May-26 PEDIDOSYA*THOUSAND BURG 001818 20.730,00	f
326	8	1	2026-05-10	PEDIDOSYA*THOUSAND BURG	001829	refund	ARS	-11165.00	1	\N	committed	8:1a543498a7bc6fa252cfa85c9faeaf5141fb3ebeaf742280e8d3a1a521c14161	10-May-26 PEDIDOSYA*THOUSAND BURG 001829 -11.165,00	f
327	8	1	2026-05-12	OPENAI *CHATGPT SUBSCR	886716	purchase	USD	20.00	8	\N	committed	8:4e2bbb38e0ee6347c80d23ab82add26192d14257a1d9967e520c50fe4f8bb515	12-May-26 OPENAI *CHATGPT SUBSCR USD 20,00 886716 20,00	t
328	8	1	2026-05-28	MERPAGO*WALDENCASES C.01/03	249953	payment	ARS	26250.00	\N	\N	committed	8:f63aa6884be31d1f9e78e7904f1a5c3c29ccfdd4d568f62d999c8d91b3c97bbc	13-May-26 MERPAGO*WALDENCASES C.01/03 249953 26.250,00	f
329	8	1	2026-05-14	DISCO SM 037	182760	purchase	ARS	163472.90	2	\N	committed	8:a70518ebf77eff95ddc087076dd76a0f56293bed2dd5565436b7bb23bfb9d4f9	14-May-26 DISCO SM 037 182760 163.472,90	f
330	8	1	2026-05-15	CLARO DEB AUT 000021326330519	000001	purchase	ARS	27211.25	3	5	committed	8:2427cbcb9cbc0348de94ff9a4e27c0c86121942fd7913a5e85d9f790b23505ff	15-May-26 CLARO DEB AUT 000021326330519 000001 27.211,25	t
331	8	1	2026-05-18	METROGAS SA DEB 020307417400	774893	purchase	ARS	41824.69	3	3	committed	8:2ec838b539cf86f2fd243183781158eba2f47831c273527ea5367accbc6ab7e2	18-May-26 METROGAS SA DEB 020307417400 774893 41.824,69	t
332	8	1	2026-05-18	AMAZON PRIME*TT9 f9vrF5l8d	754142	purchase	USD	14.99	8	\N	committed	8:6ec085dfd39af2a7284460fa1e35a647e14a28de52a7e15fbcd9a63a38da5328	18-May-26 AMAZON PRIME*TT9 f9vrF5l8dUSD 14,99 754142 14,99	t
333	8	1	2026-05-18	STEAMGAMES.COM 4 425952298	679109	purchase	USD	8.99	11	\N	committed	8:111fd27547b17ce90e16e19aabac505dece03d9e288d855a3bb066bb224354c9	18-May-26 STEAMGAMES.COM 4 425952298USD 8,99 679109 8,99	f
334	8	1	2026-05-19	CAJA SEG-PROMO BB023838068 -0	000001	purchase	ARS	200621.00	7	7	committed	8:a68c5e9356d06d6283a8192ad39829396c72923f0556dc656bf7897b1e531abe	19-May-26 CAJA SEG-PROMO BB023838068 -0 000001 200.621,00	t
335	8	1	2026-05-19	DLO*PEDIDOSYA PROPINA	006683	purchase	ARS	600.00	1	\N	committed	8:ff9dcbc3fdf576a287ac58fd9b716766a053ac6335fa5e8670095bafcacb8b92	19-May-26 DLO*PEDIDOSYA PROPINA 006683 600,00	f
336	8	1	2026-05-19	PEDIDOSYA*CUQUET HOUSE	003372	purchase	ARS	12530.00	1	\N	committed	8:5c5416306d82b389f586f4535329362b33d3c2d2c0070aa43d64d4b2adb2423f	19-May-26 PEDIDOSYA*CUQUET HOUSE 003372 12.530,00	f
337	8	1	2026-05-21	MERPAGO*LUVIKSA	775270	payment	ARS	128757.00	\N	\N	committed	8:e6b5a19cb13cd13a109464f1766ae7a071efdec995f0a543f931241b4cab76ce	21-May-26 MERPAGO*LUVIKSA 775270 128.757,00	f
304	8	1	2026-05-05	SU PAGO EN PESOS	\N	previous_payment	ARS	-3473786.04	\N	\N	ignored	8:5e7a3dbf3a2f6cf2952e05f07db799c218b07a876c2117f65260d96fee302d92	05-May-26 SU PAGO EN PESOS -3.473.786,04	f
305	8	1	2026-05-05	SU PAGO EN USD	\N	previous_payment	USD	-56.06	\N	\N	ignored	8:994687b8ee04110b8feed32964edb64bb07716e9b6236f1e9e2f2dba48ac9028	05-May-26 SU PAGO EN USD -56,06	f
352	8	1	2026-05-28	DEV COMISION CTA PWORLD	\N	fee	ARS	-57599.07	3	\N	committed	8:7a7b1fae86b1df23016f30a92d98de96b0a1974871bba1e00c9652bf926f281c	28-May-26 DEV COMISION CTA PWORLD -57.599,07	t
568	14	1	2026-07-02	PAGO DE SERVICIOS TARJETA 18073039 OP3802	\N	debit_purchase	ARS	-38579.44	3	\N	committed	14:e1560ed942254ab06c604f9e9edb2718	02/07/2026 | PAGO DE SERVICIOS TARJETA 18073039 OP3802 | 100 - BANCA ONLINE | -38.579,44 | 961.027,56	t
570	14	1	2026-07-01	TRANSFERENCIA	\N	transfer	ARS	-210162.00	\N	\N	committed	14:73a640cb2d7640b94fcd7519d8bc6afa	01/07/2026 | TRANSFERENCIA | 100 - BANCA ONLINE | -210.162,00 | 1.119.107,00	f
571	14	1	2026-07-01	INTERESES GANADOS	\N	income	ARS	37.60	\N	\N	committed	14:98bed32193b1795ec351679a4344da28	01/07/2026 | INTERESES GANADOS | 316 - CATALINAS | 37,60 | 1.329.269,00	f
572	14	1	2026-06-30	PAGO DE SERVICIOS TARJETA 18073039 OP9422	\N	debit_purchase	ARS	-38362.49	3	\N	committed	14:521c119c16f18a069b436025be6d700f	30/06/2026 | PAGO DE SERVICIOS TARJETA 18073039 OP9422 | 100 - BANCA ONLINE | -38.362,49 | 1.329.231,40	t
573	14	1	2026-06-30	PAGO DE SERVICIOS TARJETA 18073039 OP2788	\N	debit_purchase	ARS	-37827.74	3	\N	committed	14:96cbf73ecd1746e0ddbcc585eae113d8	30/06/2026 | PAGO DE SERVICIOS TARJETA 18073039 OP2788 | 100 - BANCA ONLINE | -37.827,74 | 1.367.593,89	t
574	14	1	2026-06-30	PAGO DE SERVICIOS TARJETA 18073039 OP5446	\N	debit_purchase	ARS	-16580.10	3	\N	committed	14:97dfc9c895daffbc34b62fc0ee68bf1a	30/06/2026 | PAGO DE SERVICIOS TARJETA 18073039 OP5446 | 100 - BANCA ONLINE | -16.580,10 | 1.405.421,63	t
575	14	1	2026-06-30	TRANSFERENCIA	\N	transfer	ARS	-60000.00	13	\N	committed	14:96870141bf0fdad57ff6585931610b3a	30/06/2026 | TRANSFERENCIA | 100 - BANCA ONLINE | -60.000,00 | 1.422.001,73	f
576	14	1	2026-06-22	TRANSFERENCIA	\N	income	ARS	115000.00	13	\N	committed	14:116a831064e706c04bc7774b9ef43c41	22/06/2026 | TRANSFERENCIA | 733 - | 115.000,00 | 1.482.001,73	f
577	14	1	2026-06-18	TRANSFERENCIA	\N	transfer	ARS	-50000.00	13	\N	committed	14:59c8deb6c9d67ce5e1992c3baddcbd96	18/06/2026 | TRANSFERENCIA | 100 - BANCA ONLINE | -50.000,00 | 1.367.001,73	f
578	14	1	2026-06-17	TRANSF. CLIENTE CTA. CAP027 027024 8 Nro:00010008	\N	income	ARS	290800.00	\N	\N	committed	14:ef20062cf0d6fa2ae16a7911ad42db70	17/06/2026 | TRANSF. CLIENTE CTA. CAP027 027024 8 Nro:00010008 | 104 - BANCA MOVIL | 290.800,00 | 1.417.001,73	f
582	14	1	2026-06-11	TRANSFERENCIA CCP316 316621 5 Nro:00010008	\N	transfer	ARS	-50000.00	\N	\N	committed	14:36bfa136a1bf420da062dd6e2aeb347f	11/06/2026 | TRANSFERENCIA CCP316 316621 5 Nro:00010008 | 100 - BANCA ONLINE | -50.000,00 | 20.250,00	f
584	14	1	2026-06-05	PAGO CON VISA DEBITO 18073039 OP4102	\N	debit_purchase	ARS	-349850.36	\N	\N	committed	14:ed7125e4cc03c4ae6025f88c6375aae9	05/06/2026 | PAGO CON VISA DEBITO 18073039 OP4102 | 733 - | -349.850,36 | 0,00	f
585	14	1	2026-06-05	PAGO DE SERVICIOS TARJETA 18073039 OP8518	\N	debit_purchase	ARS	-36539.04	3	\N	committed	14:66af456440b6e310c65c4fdc2c7bbb4d	05/06/2026 | PAGO DE SERVICIOS TARJETA 18073039 OP8518 | 100 - BANCA ONLINE | -36.539,04 | 349.850,36	t
586	14	1	2026-06-05	PAGO DE SERVICIOS TARJETA 18073039 OP8363	\N	debit_purchase	ARS	-16187.00	3	\N	committed	14:4b134fbe387101cc9525c57970039d24	05/06/2026 | PAGO DE SERVICIOS TARJETA 18073039 OP8363 | 100 - BANCA ONLINE | -16.187,00 | 386.389,40	t
588	14	1	2026-06-05	TRANSFERENCIA CCP316 316621 5	\N	income	ARS	49174.99	\N	\N	committed	14:41746b46aca9a52aed9a292a61c35a2b	05/06/2026 | TRANSFERENCIA CCP316 316621 5 | 316 - CATALINAS | 49.174,99 | 1.546.328,31	f
592	14	1	2026-06-01	REINTEGRO PROMO BBVA. 20% en Disco &	\N	income	ARS	25000.00	2	\N	committed	14:d3519e968f89a5ebca3b5fa0a086fc32	01/06/2026 | REINTEGRO PROMO BBVA. 20% en Disco & | 246 - APP MODO | 25.000,00 | 158.751,13	f
593	14	1	2026-06-01	INTERESES GANADOS	\N	income	ARS	16.92	\N	\N	committed	14:269dd58a55405288f11adbef8d496261	01/06/2026 | INTERESES GANADOS | 316 - CATALINAS | 16,92 | 133.751,13	f
594	14	1	2026-05-21	TRANSFERENCIA CAP027 027024 8 Nro:00010008	\N	transfer	ARS	-130000.00	\N	\N	committed	14:837552e350090144209aeede3be77255	21/05/2026 | TRANSFERENCIA CAP027 027024 8 Nro:00010008 | 104 - BANCA MOVIL | -130.000,00 | 133.734,21	f
595	14	1	2026-05-19	TRANSFERENCIA	\N	transfer	ARS	-446976.00	13	\N	committed	14:7bb8ea6644e8516f8a83b2dd0d30d5c1	19/05/2026 | TRANSFERENCIA | 100 - BANCA ONLINE | -446.976,00 | 263.734,21	f
596	14	1	2026-05-19	TRANSFERENCIA	\N	transfer	ARS	-50000.00	2	22	committed	14:950b0541f71e24a7591a3ab6cb77b4c9	19/05/2026 | TRANSFERENCIA | 100 - BANCA ONLINE | -50.000,00 | 710.710,21	f
597	14	1	2026-05-19	TRANSFERENCIA	\N	income	ARS	82600.00	13	\N	committed	14:3a14925b0deeb2041058d77e6d593863	19/05/2026 | TRANSFERENCIA | 733 - | 82.600,00 | 760.710,21	f
471	11	1	2026-03-21	VICTORIA BROWN	000352	purchase	ARS	166000.00	\N	\N	committed	11:9310f35a3794109a480783eae6e1330d7d6ed5953363735cfb48c83cd3c6cd80	21-Mar-26 VICTORIA BROWN 000352 166.000,00	f
472	11	1	2026-03-21	PAYU*AR*UBER	007369	purchase	ARS	19615.00	\N	\N	committed	11:fa610ae1f7c8bc9f238fdb3dec4bc85f9d6233bd0bc3ad67492572b73639692f	21-Mar-26 PAYU*AR*UBER 007369 19.615,00	f
473	11	1	2026-03-25	METROGAS SA DEB 020307417400	753611	purchase	ARS	37275.45	3	3	committed	11:89d2edba1ef93f6cf2a2f9b65ae5f675bb786b83e8912d53fbc56339f6aa0787	25-Mar-26 METROGAS SA DEB 020307417400 753611 37.275,45 Impuestos, cargos e intereses	t
474	11	1	2026-02-26	COMISION CTA PWORLD	\N	fee	ARS	61157.02	3	\N	committed	11:74ae3b62beba899fe33e802bd2de793839fa59ce8808bf709980af488c828a9e	26-Feb-26 COMISION CTA PWORLD 61.157,02	t
475	11	1	2026-03-26	DB IVA $ 21% 61.157,02	\N	tax	ARS	12842.97	4	\N	committed	11:1f8ee35231152ce8c1360a84231af2ae5e68d1eb262f9507fbe39f930fa9bb7a	26-Mar-26 DB IVA $ 21% 61.157,02 12.842,97	f
476	11	1	2026-03-26	IIBB PERCEP-CABA 2,00%( 20648,72)	\N	tax	ARS	412.97	4	\N	committed	11:0e7c454ca92ad806b766479f8c63546d03588f7267f33c6d32c62a2b271d8691	26-Mar-26 IIBB PERCEP-CABA 2,00%( 20648,72) 412,97	f
477	11	1	2026-03-26	IVA RG 4240 21%( 20648,72)	\N	tax	ARS	4336.23	4	\N	committed	11:fa33bcaff11b9262e0e0a920aaa4da5af918e991447e7f17f116eb33626f1f4e	26-Mar-26 IVA RG 4240 21%( 20648,72) 4.336,23	f
478	11	1	2026-03-26	DB.RG 5617 30% ( 20648,72 )	\N	tax	ARS	6194.61	4	\N	committed	11:f44337f2492c5382007edb496bb062261c287a3c9cbeaa070935a55d035ac5d4	26-Mar-26 DB.RG 5617 30% ( 20648,72 ) 6.194,61	f
599	14	1	2026-05-05	TRANSFERENCIA CAP027 027024 8 Nro:00010008	\N	transfer	ARS	-1000000.00	13	\N	committed	14:88cb9362c1cec92f5df493e596584f2b	05/05/2026 | TRANSFERENCIA CAP027 027024 8 Nro:00010008 | 100 - BANCA ONLINE | -1.000.000,00 | 4.151.896,25	f
602	14	1	2026-05-04	INTERESES GANADOS	\N	income	ARS	19.09	\N	\N	committed	14:c1d5e34655f2377170331a4ed226fcff	04/05/2026 | INTERESES GANADOS | 316 - CATALINAS | 19,09 | 216.112,70	f
603	14	1	2026-04-27	Transferencia inmediata	\N	transfer	ARS	-100000.00	\N	\N	committed	14:c7f157bc881e6d2265816cfa34f6a810	27/04/2026 | Transferencia inmediata | 100 - BANCA ONLINE | -100.000,00 | 216.093,61	f
604	14	1	2026-04-27	PAGO DE SERVICIOS TARJETA 18073039 OP1619	\N	debit_purchase	ARS	-36539.04	3	\N	committed	14:357c518d2068ef0a1fd80b852f48072f	27/04/2026 | PAGO DE SERVICIOS TARJETA 18073039 OP1619 | 100 - BANCA ONLINE | -36.539,04 | 316.093,61	t
605	14	1	2026-04-27	PAGO DE SERVICIOS TARJETA 18073039 OP5935	\N	debit_purchase	ARS	-15703.10	3	\N	committed	14:8f9f9cec5354a12c1a014fae73e08175	27/04/2026 | PAGO DE SERVICIOS TARJETA 18073039 OP5935 | 100 - BANCA ONLINE | -15.703,10 | 352.632,65	t
606	14	1	2026-04-27	TRANSFERENCIA	\N	income	ARS	24000.00	13	\N	committed	14:4759f7b475e467e00335933359eb7c66	27/04/2026 | TRANSFERENCIA | 733 - | 24.000,00 | 368.335,75	f
607	14	1	2026-04-27	TRANSF. CLIENTE CTA. CAP999 277484 1 Nro:00010008	\N	income	ARS	12000.00	\N	\N	committed	14:63fe0428dd836eefafaf0d4c345ee792	27/04/2026 | TRANSF. CLIENTE CTA. CAP999 277484 1 Nro:00010008 | 104 - BANCA MOVIL | 12.000,00 | 344.335,75	f
608	14	1	2026-04-24	TRANSFERENCIA	\N	transfer	ARS	-30000.00	13	\N	committed	14:30b9f5cab6ee1db8c6731f252a17841d	24/04/2026 | TRANSFERENCIA | 100 - BANCA ONLINE | -30.000,00 | 332.335,75	f
609	14	1	2026-04-21	Transferencia inmediata	\N	transfer	ARS	-1370000.00	13	\N	committed	14:db609332399374208efdd43919b649c2	21/04/2026 | Transferencia inmediata | 100 - BANCA ONLINE | -1.370.000,00 | 362.335,75	f
612	14	1	2026-04-20	DEBITO DIRECTO	\N	debit_purchase	ARS	-194300.32	\N	\N	committed	14:006629d4603d899c0c8b7f009df6f299	20/04/2026 | DEBITO DIRECTO | 569 - MEDIOS DE PAGO - SERVICIO | -194.300,32 | 334.764,59	f
613	14	1	2026-04-13	TRANSFERENCIA	\N	transfer	ARS	-100000.00	13	\N	committed	14:6506991d23fd046cfc0e0641110a44f8	13/04/2026 | TRANSFERENCIA | 100 - BANCA ONLINE | -100.000,00 | 529.064,91	f
614	14	1	2026-04-13	Transferencia inmediata	\N	transfer	ARS	-214300.00	13	\N	committed	14:cdb85ed331f37c23048cb67d87a778f7	13/04/2026 | Transferencia inmediata | 100 - BANCA ONLINE | -214.300,00 | 629.064,91	f
307	8	1	2026-05-28	CR IVA $ 21 %	\N	tax	ARS	-12095.80	4	\N	committed	8:e3da994055c64ac5dd6d1193f32099910a8c79aeb28834a356d9c3152a29bf48	28-May-26 CR IVA $ 21 % -12.095,80	f
616	14	1	2026-04-08	PAGO DE SERVICIOS TARJETA 18073039 OP8708	\N	debit_purchase	ARS	-35946.61	3	\N	committed	14:c73efda3d59b038ad4f347b2151770a6	08/04/2026 | PAGO DE SERVICIOS TARJETA 18073039 OP8708 | 100 - BANCA ONLINE | -35.946,61 | 918.364,91	t
617	14	1	2026-04-08	PAGO DE SERVICIOS TARJETA 18073039 OP3682	\N	debit_purchase	ARS	-33132.40	3	\N	committed	14:128cf999ece9495e822e349aa6963491	08/04/2026 | PAGO DE SERVICIOS TARJETA 18073039 OP3682 | 100 - BANCA ONLINE | -33.132,40 | 954.311,52	t
618	14	1	2026-04-08	PAGO DE SERVICIOS TARJETA 18073039 OP7422	\N	debit_purchase	ARS	-32332.42	3	\N	committed	14:17ec0cf2eb58f00e35781631e8b3dbdd	08/04/2026 | PAGO DE SERVICIOS TARJETA 18073039 OP7422 | 100 - BANCA ONLINE | -32.332,42 | 987.443,92	t
619	14	1	2026-04-08	PAGO DE SERVICIOS TARJETA 18073039 OP9027	\N	debit_purchase	ARS	-15331.30	3	\N	committed	14:d02b288fdb1ac6f5b97bedfcf510db00	08/04/2026 | PAGO DE SERVICIOS TARJETA 18073039 OP9027 | 100 - BANCA ONLINE | -15.331,30 | 1.019.776,34	t
623	14	1	2026-04-06	Transferencia inmediata	\N	transfer	ARS	-200000.00	13	\N	committed	14:8fbbb8720777858b4e1ebbe779eed354	06/04/2026 | Transferencia inmediata | 100 - BANCA ONLINE | -200.000,00 | 253.058,28	f
624	14	1	2026-04-06	REINTEGRO PROMO BBVA. 20% en Disco &	\N	income	ARS	25000.00	2	\N	committed	14:5452bfbc67ad25b5d4ff6b293c3b504d	06/04/2026 | REINTEGRO PROMO BBVA. 20% en Disco & | 246 - APP MODO | 25.000,00 | 453.058,28	f
625	14	1	2026-04-01	INTERESES GANADOS	\N	income	ARS	32.05	\N	\N	committed	14:0e4e7275011a23717dbbf2ae35cbfb8a	01/04/2026 | INTERESES GANADOS | 316 - CATALINAS | 32,05 | 428.058,28	f
626	14	1	2026-03-27	GESTION PAGO	\N	income	ARS	3061.27	\N	\N	committed	14:52d7501ddec4d3bc900db8ccd10cd15a	27/03/2026 | GESTION PAGO | 569 - MEDIOS DE PAGO - SERVICIO | 3.061,27 | 428.026,23	f
338	8	1	2026-05-23	PEDIDOSYA*CUQUET HOUSE	004022	purchase	ARS	14430.00	1	\N	committed	8:f2a55c1fd9ec2a990c4e1292af29adbfc64a8777cf9d0de0b1dd6cc4f90caf38	23-May-26 PEDIDOSYA*CUQUET HOUSE 004022 14.430,00	f
339	8	1	2026-05-24	PEDIDOSYA*DER GRUND TEM	004446	purchase	ARS	41390.00	1	\N	committed	8:9f6b19464602789ffc18785e637a1f10070d248981abec807c2855eaa006f042	24-May-26 PEDIDOSYA*DER GRUND TEM 004446 41.390,00	f
340	8	1	2026-05-24	STEAMGAMES.COM 4259522985	915707	purchase	USD	19.99	11	33	committed	8:ab721e3317fb741fd1704559967bd843b5324e244130039dae5285c92f33c8bb	24-May-26 STEAMGAMES.COM 4259522985 USD 19,99 915707 19,99	f
341	8	1	2026-05-25	DLO*PEDIDOSYA PROPINA	002436	purchase	ARS	800.00	1	\N	committed	8:24f68f3f34b4a15ccbdf4a0f215ab10e129d3ef9b93c9c56638de7d11a533ffa	25-May-26 DLO*PEDIDOSYA PROPINA 002436 800,00	f
342	8	1	2026-05-26	PEDIDOSYA*GLORIOSO CHUR	004605	purchase	ARS	11630.00	1	\N	committed	8:12e256c2efaa771cab350b6615db7c08211316137a3f3312d8c68788acec07c7	26-May-26 PEDIDOSYA*GLORIOSO CHUR 004605 11.630,00	f
343	8	1	2026-05-27	OSDE 000062938930501	001840	purchase	ARS	202741.53	6	\N	committed	8:b155bc139a0ffb35ae72eef7d17add5727baafd9b365ad5145384940c8a2b7cb	27-May-26 OSDE 000062938930501 001840 202.741,53	f
344	8	1	2026-05-27	STEAMGAMES.COM 4259522985	115006	purchase	USD	5.62	11	33	committed	8:9dff652db1ffb7659e0226653fc5b5f836d6e36d9f9b30baa667dab7e917dc46	27-May-26 STEAMGAMES.COM 4259522985 USD 5,62 115006 5,62 Impuestos, cargos e intereses	f
345	8	1	2026-04-30	COMISION CTA PWORLD	\N	fee	ARS	57599.07	3	\N	committed	8:9368daeb66db20b8df8e7d15a4f697f9e346b14cf13bfb3e9ddec4ae4d3a81d5	30-Abr-26 COMISION CTA PWORLD 57.599,07	t
346	8	1	2026-05-28	DB IVA $ 21% 57.599,07	\N	tax	ARS	12095.80	4	\N	committed	8:f55c1de8b3b4d5b397eba4651ce1d1e4e8ce84d7ebf9f6070ec33192266eb17d	28-May-26 DB IVA $ 21% 57.599,07 12.095,80	f
347	8	1	2026-05-28	IIBB PERCEP-CABA 2,00%( 33871,75)	\N	tax	ARS	677.43	4	\N	committed	8:5e3876f7bf64e4eed3b7a16d2e49185812e0f6ffd4b7e14bc3c08d75b3f374b1	28-May-26 IIBB PERCEP-CABA 2,00%( 33871,75) 677,43	f
348	8	1	2026-05-28	IIBB PERCEP-CABA 2,00%( 36174,12)	\N	tax	ARS	723.48	4	\N	committed	8:b559d084be3c3c036946558c9c8c4b21ab034551b0ea9aa5050a9d577de0a668	28-May-26 IIBB PERCEP-CABA 2,00%( 36174,12) 723,48	f
349	8	1	2026-05-28	IVA RG 4240 21%( 33871,75)	\N	tax	ARS	7113.06	4	\N	committed	8:8d3f4ea3915e9249f4517b2586cf092c362df449a06d6f77b844c3a8b3b04782	28-May-26 IVA RG 4240 21%( 33871,75) 7.113,06	f
350	8	1	2026-05-28	IVA RG 4240 21%( 36174,12)	\N	tax	ARS	7596.56	4	\N	committed	8:a11354c55094e72259a5c863fe9aab7934bb2da989a2e05450b589230f944c7e	28-May-26 IVA RG 4240 21%( 36174,12) 7.596,56	f
351	8	1	2026-05-28	DB.RG 5617 30% ( 49423,37 )	\N	tax	ARS	14827.01	4	\N	committed	8:71fc224576f309c8d4b5319a4f017be3cb94e03e698f0010ad34d092e02dc5d0	28-May-26 DB.RG 5617 30% ( 49423,37 ) 14.827,01 (cid:204)(cid:103)(cid:183)(cid:125)(cid:163)(cid:111)(cid:108)(cid:105)(cid:203) 3-91300005-03 .orN TIUC otpircsnI elbasnopseR AVI - .A.S anitnegrA AVBB ocnaB	f
627	14	1	2026-03-25	TRANSFERENCIA	\N	transfer	ARS	-328354.00	3	\N	committed	14:a95f06a9d269adee2fd3c3e8f18d8a54	25/03/2026 | TRANSFERENCIA | 100 - BANCA ONLINE | -328.354,00 | 424.964,96	t
143	4	1	2026-02-26	MERPAGO*MERCADOLIBRE C.03/06	821025	payment	ARS	9998.33	\N	\N	committed	4:3f1b9c56995bb8d9f2f19917b1d536d19f107cf01969233c9cbeed56bbf98629	03-Dic-25 MERPAGO*MERCADOLIBRE C.03/06 821025 9.998,33	f
144	4	1	2026-02-26	MERPAGO*MUNDOFIX C.02/02	423066	payment	ARS	54999.50	\N	\N	committed	4:ba7a654342923aaa65b77f6cfb6e8f2acf7ef0e9835de49ca2d9a6531520ce23	14-Ene-26 MERPAGO*MUNDOFIX C.02/02 423066 54.999,50	f
145	4	1	2026-02-26	MERPAGO*KAMADOARGENTI C.01/03	826550	payment	ARS	14412.34	\N	\N	committed	4:09b91ed6d8c684970db4fd7dbda74925218e61bacc64131a82b06aa66f4994f9	30-Ene-26 MERPAGO*KAMADOARGENTI C.01/03 826550 14.412,34	f
146	4	1	2026-01-31	PEDIDOSYA*HARRYS KILLER	009413	purchase	ARS	36150.00	1	\N	committed	4:91aeac2c968dbabdecc492ec98a93bb013e71c9bdcbca0bafd68793babadbc17	31-Ene-26 PEDIDOSYA*HARRYS KILLER 009413 36.150,00	f
628	14	1	2026-03-25	TRANSFERENCIA	\N	income	ARS	6000.00	2	\N	committed	14:1373015e114a8f98f09621ca53f4bd79	25/03/2026 | TRANSFERENCIA | 733 - | 6.000,00 | 753.318,96	t
629	14	1	2026-03-25	TRANSFERENCIA	\N	income	ARS	88000.00	2	\N	committed	14:2ebad6debad0281d787f83496cef202a	25/03/2026 | TRANSFERENCIA | 733 - | 88.000,00 | 747.318,96	f
630	14	1	2026-03-20	DEBITO DIRECTO	\N	debit_purchase	ARS	-194300.32	4	\N	committed	14:b66c6518082c0d0728a9a95e31b88bd9	20/03/2026 | DEBITO DIRECTO | 569 - MEDIOS DE PAGO - SERVICIO | -194.300,32 | 659.318,96	f
631	14	1	2026-03-20	TRANSFERENCIA	\N	income	ARS	143585.00	2	\N	committed	14:fcf09edb4af5bdc60b8c75bf58caac4c	20/03/2026 | TRANSFERENCIA | 733 - | 143.585,00 | 853.619,28	f
632	14	1	2026-03-10	PAGO DE SERVICIOS TARJETA 18073039 OP3266	\N	debit_purchase	ARS	-32332.42	3	\N	committed	14:fa9c78d2d1a1854821e1ef6ad580bc8c	10/03/2026 | PAGO DE SERVICIOS TARJETA 18073039 OP3266 | 100 - BANCA ONLINE | -32.332,42 | 710.034,28	t
633	14	1	2026-03-10	PAGO DE SERVICIOS TARJETA 18073039 OP1997	\N	debit_purchase	ARS	-31814.94	3	\N	committed	14:f19f1d21fa905c679efd0333466dcfe4	10/03/2026 | PAGO DE SERVICIOS TARJETA 18073039 OP1997 | 100 - BANCA ONLINE | -31.814,94 | 742.366,70	t
634	14	1	2026-03-10	PAGO DE SERVICIOS TARJETA 18073039 OP3086	\N	debit_purchase	ARS	-14938.20	3	\N	committed	14:c0ab6295291e5a8cf32354cfc81281e6	10/03/2026 | PAGO DE SERVICIOS TARJETA 18073039 OP3086 | 100 - BANCA ONLINE | -14.938,20 | 774.181,64	t
635	14	1	2026-03-05	TRANSFERENCIA	\N	transfer	ARS	-200000.00	2	\N	committed	14:b6507b97f567125dd26a970e8ed1b513	05/03/2026 | TRANSFERENCIA | 100 - BANCA ONLINE | -200.000,00 | 789.119,84	f
640	14	1	2026-03-02	INTERESES GANADOS	\N	income	ARS	23.91	\N	\N	committed	14:7fd734603caaba2f136c1220add95052	02/03/2026 | INTERESES GANADOS | 316 - CATALINAS | 23,91 | 1.000.952,89	f
642	14	1	2026-02-20	DEBITO DIRECTO	\N	debit_purchase	ARS	-194300.32	4	\N	committed	14:243450447499fb457b7afbd8d10f194c	20/02/2026 | DEBITO DIRECTO | 569 - MEDIOS DE PAGO - SERVICIO | -194.300,32 | 1.400.928,98	f
645	14	1	2026-02-19	TRANSFERENCIA	\N	income	ARS	24400.00	13	\N	committed	14:af374ed4e45cb3f66efdfce1e70f4332	19/02/2026 | TRANSFERENCIA | 733 - | 24.400,00 | 208.288,79	f
173	5	1	2026-01-29	PLATEANET C.03/03	001049	purchase	ARS	96000.00	\N	\N	committed	5:5e25b482487c7702d25ac8b90d8656e69c0fbefe5a1e0521cd827b38ce6a90b5	06-Nov-25 PLATEANET C.03/03 001049 96.000,00	f
174	5	1	2026-01-29	MERPAGO*MERCADOLIBRE C.02/06	821025	payment	ARS	9998.33	\N	\N	committed	5:8566589ed3455b845979b9480bdd14e41c344a0448e6bb4f08543cbd1353737c	03-Dic-25 MERPAGO*MERCADOLIBRE C.02/06 821025 9.998,33	f
175	5	1	2026-01-02	MERPAGO*GAEDSH	015427	payment	ARS	28755.99	\N	\N	committed	5:86b4b01b31a54d69d7754d9a3cd6e7fcf3334ac1eac50823919dd131e938ca81	02-Ene-26 MERPAGO*GAEDSH 015427 28.755,99	f
176	5	1	2026-01-03	DLO*PEDIDOSYA PLUS	007512	purchase	ARS	5490.00	1	\N	committed	5:0d2ccddd51af97e05f0b69f70815f3524288f5e5a9f3f3b95ead7ebb42eb5b45	03-Ene-26 DLO*PEDIDOSYA PLUS 007512 5.490,00 3-91300005-03 .orN TIUC otpircsnI elbasnopseR AVI - .A.S anitnegrA AVBB ocnaB	f
177	5	1	2026-01-04	MERPAGO*TADA	279471	payment	ARS	68550.00	\N	\N	committed	5:d25b6e8e2ed1c7de74c290074a3b71b922c8b42c670d7f65a965c7096ded354f	04-Ene-26 MERPAGO*TADA 279471 68.550,00	f
178	5	1	2026-01-05	PEDIDOSYA*GLORIOSO CHUR	005981	purchase	ARS	11390.00	1	\N	committed	5:0d598ac9792f60b75291c9f863a47fd2623e6cb3df27823a97f5610c2f68f1bd	05-Ene-26 PEDIDOSYA*GLORIOSO CHUR 005981 11.390,00	f
179	5	1	2026-01-06	MERPAGO*MERCADOLIBRE	244352	payment	ARS	64072.00	\N	\N	committed	5:5678e7595dec261d479562a1613b9fb0e876e48b79928df9d37e8da3b52ff607	06-Ene-26 MERPAGO*MERCADOLIBRE 244352 64.072,00	f
180	5	1	2026-01-06	DISCO SM 037	229136	purchase	ARS	76206.22	2	\N	committed	5:945045f0a1966f7100fc5c632d3115ab287099c833ad1128b52cc3af7ec495a2	06-Ene-26 DISCO SM 037 229136 76.206,22	f
181	5	1	2026-01-08	MOVISTAR HOGAR 000000568729017	000001	purchase	ARS	42209.99	3	5	committed	5:8cb57b404f1b87c2298ae0e7ec4bb9e3561ed7fa6fd32e6680974c8812362272	08-Ene-26 MOVISTAR HOGAR 000000568729017 000001 42.209,99	f
182	5	1	2026-01-10	PEDIDOSYA*HARRYS KILLER	008262	purchase	ARS	17390.00	1	\N	committed	5:12ae9a4dc9f5b640659d2e1bcdd4d4713af7e8ecdf8ba53a76e7f478a5090ec1	10-Ene-26 PEDIDOSYA*HARRYS KILLER 008262 17.390,00	f
183	5	1	2026-01-13	MERPAGO*REX	785083	payment	ARS	100056.45	\N	\N	committed	5:094c7e4956598391992ffee51ac7ce2673bab0f417e8e7af95ad3e56e5df337d	13-Ene-26 MERPAGO*REX 785083 100.056,45	f
184	5	1	2026-01-13	EDESUR	004083	purchase	ARS	278614.46	\N	\N	committed	5:42b01c8f8bdb24111c5298396d398b5d3652cc5b4e6971f6bf848463b318c2d6	13-Ene-26 EDESUR 004083 278.614,46	f
185	5	1	2026-01-29	MERPAGO*MUNDOFIX C.01/02	423066	payment	ARS	54999.50	\N	\N	committed	5:df0cb0026c48b85a2a9c6fa5626d3c98203ee8d48ce91ac06e69b4cb76cd34d5	14-Ene-26 MERPAGO*MUNDOFIX C.01/02 423066 54.999,50	f
186	5	1	2026-01-15	PEDIDOSYA*KFC ADROGUE	001046	purchase	ARS	27610.00	1	\N	committed	5:3e5fdec5338bc59e888202d4e4a376828169eeec437c42478b535365e6758046	15-Ene-26 PEDIDOSYA*KFC ADROGUE 001046 27.610,00	f
187	5	1	2026-01-16	CLARO DEB AUT 000021326330519	000001	purchase	ARS	23066.99	3	5	committed	5:d02d2cacf0a7b3b5fb9cded04ea3d0275924d47ae2c50997f790fdab2b533391	16-Ene-26 CLARO DEB AUT 000021326330519 000001 23.066,99	f
188	5	1	2026-01-16	METROGAS SA DEB 020307417400	650342	purchase	ARS	40011.88	3	3	committed	5:79814f8d0926abead54125a0b2757367f697ac8e3ee9b10b75d3c9e06b35247f	16-Ene-26 METROGAS SA DEB 020307417400 650342 40.011,88	f
646	14	1	2026-02-18	TRANSFERENCIA	\N	transfer	ARS	-150000.00	13	\N	committed	14:57fec1d2f31a470fa59b504b33f4c2ba	18/02/2026 | TRANSFERENCIA | 100 - BANCA ONLINE | -150.000,00 | 183.888,79	f
647	14	1	2026-02-18	TRANSF. CLIENTE CTA. CAP184 311532 8 Nro:00010008	\N	income	ARS	32300.00	\N	\N	committed	14:c0ddf7f4669b4615b04ef2a27708547c	18/02/2026 | TRANSF. CLIENTE CTA. CAP184 311532 8 Nro:00010008 | 104 - BANCA MOVIL | 32.300,00 | 333.888,79	f
648	14	1	2026-02-18	TRANSF. CLIENTE CTA. CAP316 427769 9 Nro:00010008	\N	income	ARS	32500.00	\N	\N	committed	14:e3326f434a1d45374a4def67060349d2	18/02/2026 | TRANSF. CLIENTE CTA. CAP316 427769 9 Nro:00010008 | 100 - BANCA ONLINE | 32.500,00 | 301.588,79	f
649	14	1	2026-02-11	PAGO DE SERVICIOS TARJETA 18073039 OP6471	\N	debit_purchase	ARS	-32979.07	3	\N	committed	14:ac82fcdfc3695a31fb61f7da514aa8d6	11/02/2026 | PAGO DE SERVICIOS TARJETA 18073039 OP6471 | 100 - BANCA ONLINE | -32.979,07 | 269.088,79	t
650	14	1	2026-02-11	PAGO DE SERVICIOS TARJETA 18073039 OP1526	\N	debit_purchase	ARS	-31427.40	3	\N	committed	14:e068cd3619785420b8a6f7c71349f293	11/02/2026 | PAGO DE SERVICIOS TARJETA 18073039 OP1526 | 100 - BANCA ONLINE | -31.427,40 | 302.067,86	t
651	14	1	2026-02-11	PAGO DE SERVICIOS TARJETA 18073039 OP3417	\N	debit_purchase	ARS	-30591.26	3	\N	committed	14:63ce7a388f8e838b9325c594a5bd1402	11/02/2026 | PAGO DE SERVICIOS TARJETA 18073039 OP3417 | 100 - BANCA ONLINE | -30.591,26 | 333.495,26	t
652	14	1	2026-02-10	Transferencia inmediata	\N	transfer	ARS	-194300.32	13	\N	committed	14:fe0f68141bf1cbdc091b5e629bfe281b	10/02/2026 | Transferencia inmediata | 100 - BANCA ONLINE | -194.300,32 | 364.086,52	f
579	14	1	2026-06-11	CUENTA VISA NRO. 79083843369698	\N	card_payment	ARS	-252457.00	\N	\N	ignored	14:81da4faa26de5c27ee7a6ca6606be65e	11/06/2026 | CUENTA VISA NRO. 79083843369698 | 316 - CATALINAS | -252.457,00 | 1.126.201,73	f
587	14	1	2026-06-05	CUENTA VISA NRO. 79083843369698	\N	card_payment	ARS	-1143751.91	\N	\N	ignored	14:07f1ac240915610fbbe2df43a8edcac8	05/06/2026 | CUENTA VISA NRO. 79083843369698 | 316 - CATALINAS | -1.143.751,91 | 402.576,40	f
589	14	1	2026-06-05	CUENTA VISA NRO. 79083843369699	\N	card_payment	ARS	-101949.35	\N	\N	ignored	14:f8f5aa23b2998d869dca204bac7575d0	05/06/2026 | CUENTA VISA NRO. 79083843369699 | 316 - CATALINAS | -101.949,35 | 1.497.153,32	f
189	5	1	2026-01-19	SANITARIOS VAL-MAR	005808	purchase	ARS	58862.96	\N	\N	committed	5:a74a4d399432355f77da78db33c38a36f893245cd3af4e80d19df15f3e8e8076	19-Ene-26 SANITARIOS VAL-MAR 005808 58.862,96	f
190	5	1	2026-01-20	CAJA SEG-PROMO BB023838068 -0	000001	purchase	ARS	184669.00	7	7	committed	5:6124dc8c05725b885bb2ae742e503d906345fd582655138649ea8f0babd920d2	20-Ene-26 CAJA SEG-PROMO BB023838068 -0 000001 184.669,00	f
191	5	1	2026-01-26	OSDE 000062938930501	006708	purchase	ARS	159659.44	6	\N	committed	5:fe8afaecdcc975c084f29fbddfcbb85d093323cd9cf85c65c1a38bc152a4f07f	26-Ene-26 OSDE 000062938930501 006708 159.659,44 Impuestos, cargos e intereses	f
192	5	1	2025-12-31	COMISION CTA PWORLD	\N	fee	ARS	61157.02	3	\N	committed	5:c33df3d9f08be589a9cdc2107518d8dac7bfb4ce52acd5020f4581c467f98062	31-Dic-25 COMISION CTA PWORLD 61.157,02	f
171	5	1	2026-01-08	SU PAGO EN PESOS	\N	previous_payment	ARS	-1150667.21	\N	\N	ignored	5:1932d60e81db39924a02cff4260e1a063385aadd70d1cbf4e2226a4c83c15261	08-Ene-26 SU PAGO EN PESOS -1.150.667,21	f
172	5	1	2026-01-08	SU PAGO EN USD	\N	previous_payment	USD	-47.20	\N	\N	ignored	5:4b62ef19757d399d1515c1e160171ebbd4bcf316633b37c01bfbcea8be8b909f	08-Ene-26 SU PAGO EN USD -47,20	f
193	5	1	2026-01-29	DB IVA $ 21% 61.157,02	\N	tax	ARS	12842.97	4	\N	committed	5:9315a94e17fbccd3c8d20b91bce577311271bd03a32227532dc45e86635e4f88	29-Ene-26 DB IVA $ 21% 61.157,02 12.842,97	f
147	4	1	2026-02-03	DLO*PEDIDOSYA PLUS	007776	purchase	ARS	5490.00	1	\N	committed	4:06a402862d7f828bff087af38db76f15dd01bf16c6a129051896a19a44026eda	03-Feb-26 DLO*PEDIDOSYA PLUS 007776 5.490,00 3-91300005-03 .orN TIUC otpircsnI elbasnopseR AVI - .A.S anitnegrA AVBB ocnaB	f
148	4	1	2026-02-26	MERPAGO*KAMADOARGENTI C.01/06	260104	payment	ARS	31083.50	\N	\N	committed	4:f8dfbed8026e305db82f3a612793258b48975bbd96af0f8d1bae0b5243b6d6bf	04-Feb-26 MERPAGO*KAMADOARGENTI C.01/06 260104 31.083,50	f
149	4	1	2026-02-04	COTO SUCURSAL 107	494196	purchase	ARS	455750.07	\N	\N	committed	4:735df20ef8702a499da5cf7e9c9438b5032e81d41e1c877068b73061daa18ce3	04-Feb-26 COTO SUCURSAL 107 494196 455.750,07	f
150	4	1	2026-02-08	MERPAGO*EUPRO	763424	payment	ARS	50228.93	\N	\N	committed	4:ca2ea30a94a059786105141294b9034c8cf7502cc2e8f94f39b2deb24c529e05	08-Feb-26 MERPAGO*EUPRO 763424 50.228,93	f
151	4	1	2026-02-09	MERPAGO*MERCADOLIBRE	220742	payment	ARS	142941.51	\N	\N	committed	4:edb667c8f7ae753d93771f9844e7f51aa05ab92a6143907b0d8870f85d1b5d98	09-Feb-26 MERPAGO*MERCADOLIBRE 220742 142.941,51	f
152	4	1	2026-02-10	DLO*PEDIDOSYA PROPINA	004773	purchase	ARS	650.00	1	\N	committed	4:ae5c41778f6ef63a669fc7e4ff6c5ba624a67ae83f5c0cb8c21f7e7c78e0cd44	10-Feb-26 DLO*PEDIDOSYA PROPINA 004773 650,00	f
153	4	1	2026-02-10	PEDIDOSYA*HARRYS KILLER	004485	purchase	ARS	18190.00	1	\N	committed	4:ed2cbf1725f01b4a7899be6fbe71e57acda61456c9910e7c8d62b508784eb744	10-Feb-26 PEDIDOSYA*HARRYS KILLER 004485 18.190,00	f
154	4	1	2026-02-10	MOVISTAR HOGAR 000000568729017	000001	purchase	ARS	43259.99	3	5	committed	4:a4ac6d730f0314c4838b767842c5de239480f53730c0a167366939852b87c79d	10-Feb-26 MOVISTAR HOGAR 000000568729017 000001 43.259,99	t
155	4	1	2026-02-11	EDESUR	009105	purchase	ARS	111095.37	\N	\N	committed	4:be2b939ab6adf6ebb13a93b7827b0a4a110bd44b75aca71e131f01f747ef3cd2	11-Feb-26 EDESUR 009105 111.095,37	f
156	4	1	2026-02-13	DLO*PEDIDOSYA PROPINA	008854	purchase	ARS	700.00	1	\N	committed	4:dc1634c1c100650caa002c230107c19db5357a51acf71b04d76ae2f5fd362b83	13-Feb-26 DLO*PEDIDOSYA PROPINA 008854 700,00	f
157	4	1	2026-02-13	PEDIDOSYA*LUCCIANOS ADR	006084	purchase	ARS	26430.00	1	\N	committed	4:77b18845b71c33f6b1e556ded2d975b15522edb6f5b143c68a84e674846658c7	13-Feb-26 PEDIDOSYA*LUCCIANOS ADR 006084 26.430,00	f
158	4	1	2026-02-26	MERPAGO*SOHODENIMROPA C.01/03	786986	payment	ARS	40186.68	\N	\N	committed	4:4d20b3ac2b58b67d2f3c55fc7aaed5f92a84078e951dd5cb79d324b099d9e92a	16-Feb-26 MERPAGO*SOHODENIMROPA C.01/03 786986 40.186,68	f
159	4	1	2026-02-17	CLARO DEB AUT 000021326330519	000001	purchase	ARS	24103.75	3	5	committed	4:569f4ba0c8790e00bc4f68bf4bfe9342adaca03cbdb1e22ee7610ecdd841685b	17-Feb-26 CLARO DEB AUT 000021326330519 000001 24.103,75	t
160	4	1	2026-02-18	SHELL ADROGUE	007145	purchase	ARS	98000.00	\N	\N	committed	4:1d720c39cfebf9ad5e90c07ed6b0e3123948f8418213521b985b69f608787879	18-Feb-26 SHELL ADROGUE 007145 98.000,00	f
161	4	1	2026-02-19	METROGAS SA DEB 020307417400	665172	purchase	ARS	37228.78	3	3	committed	4:4221b044275e299a39619838bd9fc22c7be1c8cfd6414cb28dd67cc96f696837	19-Feb-26 METROGAS SA DEB 020307417400 665172 37.228,78	t
162	4	1	2026-02-19	CAJA SEG-PROMO BB023838068 -0	000001	purchase	ARS	190832.00	7	7	committed	4:9a2a60fd6bf39dcb9731a58853ad44ae931cc5e278bc1f9eb0a06538b30a6cbf	19-Feb-26 CAJA SEG-PROMO BB023838068 -0 000001 190.832,00	f
163	4	1	2026-02-20	MERPAGO*MERCADOLIBRE	672133	payment	ARS	86627.00	\N	\N	committed	4:386f092369a380242bc9d314ab20c2083b25ba4d66ddf8153a71a8544d49d6b9	20-Feb-26 MERPAGO*MERCADOLIBRE 672133 86.627,00	f
164	4	1	2026-02-20	MERPAGO*CMORRES	500106	payment	ARS	75485.83	\N	\N	committed	4:feb2a5a55efd73437d23d214859fbf099a961fdde4f339db8b62f9d07572d512	20-Feb-26 MERPAGO*CMORRES 500106 75.485,83	f
165	4	1	2026-02-20	DISCO SM 037	291903	purchase	ARS	80750.83	2	\N	committed	4:8eca0f6b004815d8b6e13116cc0f500b81e65598e33834c7ad9dbfe15fe98a7d	20-Feb-26 DISCO SM 037 291903 80.750,83	f
166	4	1	2026-02-26	MERPAGO*ACIUM C.01/03	513339	payment	ARS	69333.34	\N	\N	committed	4:f9399a7e13946fee91b106b8fc04626733b20380b9b31615eb4b3f8126c80fdc	21-Feb-26 MERPAGO*ACIUM C.01/03 513339 69.333,34	f
167	4	1	2026-02-22	PEDIDOSYA*LUCCIANOS ADR	001255	purchase	ARS	31860.00	1	\N	committed	4:60b781f885a06611988b989ee1f9b6b65791f514c080e54bba206fd17efa9940	22-Feb-26 PEDIDOSYA*LUCCIANOS ADR 001255 31.860,00	f
168	4	1	2026-02-24	OSDE 000062938930501	009906	purchase	ARS	157645.00	6	\N	committed	4:6e0f374994c83db01b42862da8b941cb648a17caf49c70748857102c99ae0495	24-Feb-26 OSDE 000062938930501 009906 157.645,00 Impuestos, cargos e intereses	f
169	4	1	2026-01-29	COMISION CTA PWORLD	\N	fee	ARS	61157.02	3	\N	committed	4:fe2889e91af90cece1f342473327e2869e293c87320f1609468d0b6fc98d06c0	29-Ene-26 COMISION CTA PWORLD 61.157,02	f
142	4	1	2026-02-02	SU PAGO EN PESOS	\N	previous_payment	ARS	-1421613.20	\N	\N	ignored	4:410c15f633a65294127b530757776855fbc3647c6540e5a9cfd9955e942e0289	02-Feb-26 SU PAGO EN PESOS -1.421.613,20	f
598	14	1	2026-05-05	PAGO DE TARJETA VISA Nro:00423808	\N	card_payment	ARS	-3473786.04	\N	\N	ignored	14:91aaa2a67a2154b46681fe70a5b52072	05/05/2026 | PAGO DE TARJETA VISA Nro:00423808 | 100 - BANCA ONLINE | -3.473.786,04 | 678.110,21	f
615	14	1	2026-04-09	CUENTA MASTERCARD NRO. 77126250754498	\N	card_payment	ARS	-75000.00	\N	\N	ignored	14:b2d9c1e33d27bee7120bf6a030b673b0	09/04/2026 | CUENTA MASTERCARD NRO. 77126250754498 | 316 - CATALINAS | -75.000,00 | 843.364,91	f
620	14	1	2026-04-08	PAGO DE TARJETA VISA Nro:00423808	\N	card_payment	ARS	-1755494.52	\N	\N	ignored	14:508b5d4f8d76e7598f1a004863974b43	08/04/2026 | PAGO DE TARJETA VISA Nro:00423808 | 100 - BANCA ONLINE | -1.755.494,52 | 1.035.107,64	f
170	4	1	2026-02-26	DB IVA $ 21% 61.157,02	\N	tax	ARS	12842.97	4	\N	committed	4:a49f654e6158de71bc9b81fcbddf29a8e9a07549c2477fa9773cb066a2f29eb0	26-Feb-26 DB IVA $ 21% 61.157,02 12.842,97	f
636	14	1	2026-03-03	PAGO DE TARJETA MASTERCARD Nro:00423808	\N	card_payment	ARS	-15663.95	\N	\N	ignored	14:64ba03947434fab65f3ed6fb2b069259	03/03/2026 | PAGO DE TARJETA MASTERCARD Nro:00423808 | 100 - BANCA ONLINE | -15.663,95 | 989.119,84	f
637	14	1	2026-03-03	PAGO DE TARJETA VISA Nro:00423808	\N	card_payment	ARS	-1967432.74	\N	\N	ignored	14:ac2337febef18cccb86d2339d531c64f	03/03/2026 | PAGO DE TARJETA VISA Nro:00423808 | 100 - BANCA ONLINE | -1.967.432,74 | 1.004.783,79	f
653	14	1	2026-02-04	TRANSFERENCIA	\N	transfer	ARS	-60000.00	13	\N	committed	14:3d6c17d2ff89e5cec23b8b4a4963d413	04/02/2026 | TRANSFERENCIA | 100 - BANCA ONLINE | -60.000,00 | 558.386,84	f
443	11	1	2026-03-26	MERPAGO*MERCADOLIBRE C.04/06	821025	payment	ARS	9998.33	11	\N	committed	11:f31cb1e122b2b136da8334a5b3435112223844cea5dcd9c4e9a98d9260647554	03-Dic-25 MERPAGO*MERCADOLIBRE C.04/06 821025 9.998,33	f
444	11	1	2026-03-26	MERPAGO*KAMADOARGENTI C.02/03	826550	payment	ARS	14412.33	2	14	committed	11:6ee6b1bd898a54ec36774dbc7a7952cd977c554d90dc41d8de05b83392f1e2ad	30-Ene-26 MERPAGO*KAMADOARGENTI C.02/03 826550 14.412,33 3-91300005-03 .orN TIUC otpircsnI elbasnopseR AVI - .A.S anitnegrA AVBB ocnaB	f
445	11	1	2026-03-26	MERPAGO*KAMADOARGENTI C.02/06	260104	payment	ARS	31083.50	2	14	committed	11:fa63575c57872d4500a6e9ec24a0d44cb8608ae28edb2b102062ce6c85bde731	04-Feb-26 MERPAGO*KAMADOARGENTI C.02/06 260104 31.083,50	f
446	11	1	2026-03-26	MERPAGO*SOHODENIMROPA C.02/03	786986	payment	ARS	40186.66	14	\N	committed	11:c1f7fb89a4659a869d2822be03c7549317a2d9edbd9af44b4b74132bce89b9de	16-Feb-26 MERPAGO*SOHODENIMROPA C.02/03 786986 40.186,66	f
447	11	1	2026-03-26	MERPAGO*ACIUM C.02/03	513339	payment	ARS	69333.33	13	\N	committed	11:64fe8490be2ffd02354ef2fb2a5917f52fcfbed492650ea97dfd8a1171d95f8f	21-Feb-26 MERPAGO*ACIUM C.02/03 513339 69.333,33	f
448	11	1	2026-03-01	MERPAGO*TADA	883232	payment	ARS	42000.00	\N	\N	committed	11:3645fa05200d45617c63c83bbab1b7aa219909eb2a46dd3eb9092f4baf3f55b0	01-Mar-26 MERPAGO*TADA 883232 42.000,00	f
449	11	1	2026-03-01	PEDIDOSYA*HARRYS KILLER	003769	purchase	ARS	30560.00	1	\N	committed	11:978aae16e6be2938e13ec4a4ea50e4c62945761ff2206c587407d43b6f86b269	01-Mar-26 PEDIDOSYA*HARRYS KILLER 003769 30.560,00	f
450	11	1	2026-03-02	PEDIDOSYA*TEQUESUR	005943	purchase	ARS	14300.00	1	\N	committed	11:10fdeb622579845ffb7af05ca133d4bb67caa2cf793cdc95f544c5dccb1b7a67	02-Mar-26 PEDIDOSYA*TEQUESUR 005943 14.300,00	f
451	11	1	2026-03-03	DLO*PEDIDOSYA PLUS	003939	purchase	ARS	5990.00	1	\N	committed	11:9db172a78f26ecc897363f8cd8c92d20761f4576df04cc65c55d7e459dcd5430	03-Mar-26 DLO*PEDIDOSYA PLUS 003939 5.990,00	f
452	11	1	2026-03-06	DLO*PEDIDOSYA PROPINA	004452	purchase	ARS	300.00	1	\N	committed	11:a07c4e9ed0fdfb2cce5d22532f0fe1a9e7da19385769c493e41d544adc6aae9c	06-Mar-26 DLO*PEDIDOSYA PROPINA 004452 300,00	f
453	11	1	2026-03-06	PEDIDOSYA*FABRIC SUSHI	007740	purchase	ARS	66158.00	1	\N	committed	11:65df4fe70cf11ff4c09a72c8efd44f7f4a58d158701818160318129f5643ddc0	06-Mar-26 PEDIDOSYA*FABRIC SUSHI 007740 66.158,00	f
454	11	1	2026-03-09	MERPAGO*CMORRES	727419	payment	ARS	67800.00	2	20	committed	11:c46649a17d7d62967e37dd1e4857c2c7144d493d8d54850ac2025edf27178c90	09-Mar-26 MERPAGO*CMORRES 727419 67.800,00	f
455	11	1	2026-03-10	MOVISTAR HOGAR 000000568729017	000001	purchase	ARS	44860.00	3	5	committed	11:79783fd9f8865be82d32be3ef3ab1fce88f70ac34a2ef6249253f281ed9a1189	10-Mar-26 MOVISTAR HOGAR 000000568729017 000001 44.860,00	t
456	11	1	2026-03-11	MERPAGO*DOGCENTER	984332	payment	ARS	64222.00	\N	\N	committed	11:eb910d525f50719b2cbf5fb8dfd81d29d8992bfe8cd0257d15dc2ad6aea2ed13	11-Mar-26 MERPAGO*DOGCENTER 984332 64.222,00	f
457	11	1	2026-03-13	PEDIDOSYA*HARRYS KILLER	001222	purchase	ARS	33070.00	1	\N	committed	11:56afeb5dd4866b60f06069ce1b5f90f2f2f283a5ec71235ccb316acb95741e08	13-Mar-26 PEDIDOSYA*HARRYS KILLER 001222 33.070,00	f
458	11	1	2026-03-14	DLO*PEDIDOSYA PROPINA	006152	purchase	ARS	700.00	1	\N	committed	11:48895c7c9044adab40234fb972823debf228d6b4ecc4bf91b8f7bb4d7d392af7	14-Mar-26 DLO*PEDIDOSYA PROPINA 006152 700,00	f
459	11	1	2026-03-14	PEDIDOSYA*JIRO SUSHI AD	001990	purchase	ARS	72982.00	1	\N	committed	11:e0bd3af783e01757acae317255158dc50ed93ce8eb442181964f0428eb4a97a5	14-Mar-26 PEDIDOSYA*JIRO SUSHI AD 001990 72.982,00	f
460	11	1	2026-03-15	CLARO DEB AUT 000021326330519	000001	purchase	ARS	25066.26	3	5	committed	11:f43743a3fa6911810abe4a9ffb1334a532c4c8977d77c28a253145d2b439dc7d	15-Mar-26 CLARO DEB AUT 000021326330519 000001 25.066,26	t
461	11	1	2026-03-16	EDESUR	000385	purchase	ARS	127135.77	3	1	committed	11:d4f901d7b341af14e1dac1a77595133ec4a0edd3f48ff8c6a2e9ab2de05a9862	16-Mar-26 EDESUR 000385 127.135,77	t
462	11	1	2026-03-17	CAJA SEG-PROMO BB023838068 -0	000001	purchase	ARS	196226.00	7	7	committed	11:6b26f4fa5444302f1c8db8c0ed53392af7bd6386ebcb75d97c3dcfdad4b35705	17-Mar-26 CAJA SEG-PROMO BB023838068 -0 000001 196.226,00	t
463	11	1	2026-03-17	PEDIDOSYA*PERTUTTI ADRO	003511	purchase	ARS	38570.00	1	\N	committed	11:d22907f219e3453115a5f7e91939886c53a247f0d7d9c11f9b7ed8de2687c858	17-Mar-26 PEDIDOSYA*PERTUTTI ADRO 003511 38.570,00	f
464	11	1	2026-03-17	AMAZON PRIME*BJ8 1iWVOeHn2	708962	purchase	USD	14.99	8	\N	committed	11:1bb7b20ccfcf8a5c756e849067d8198fd03bfd9e8f02496d3a35d2f2ad633b57	17-Mar-26 AMAZON PRIME*BJ8 1iWVOeHn2USD 14,99 708962 14,99	t
465	11	1	2026-03-18	MERPAGO*MERCADOLIBRE	187520	payment	ARS	126074.80	11	\N	committed	11:0ab07a015e6f45aaa7291917379701d5e1dd1f805ddf355c1886c3aae8a14206	18-Mar-26 MERPAGO*MERCADOLIBRE 187520 126.074,80	f
466	11	1	2026-03-19	PEDIDOSYA*PERTUTTI ADRO	004468	purchase	ARS	23470.00	1	\N	committed	11:98a2490e36485a7e4b434c534489c5e31b29f807751a44efc7d4dd47ba263178	19-Mar-26 PEDIDOSYA*PERTUTTI ADRO 004468 23.470,00	f
467	11	1	2026-03-20	CABIFY2612UYZHOPPT	004016	purchase	ARS	23294.19	\N	\N	committed	11:95897ca503d6fd6056c48a37222110a45dad77a5e00192ad31bfb1d3efd38955	20-Mar-26 CABIFY2612UYZHOPPT 004016 23.294,19	f
468	11	1	2026-03-20	OSDE 000062938930501	008621	purchase	ARS	188780.44	6	\N	committed	11:1fd0796f3a5743e7fd6e4344cbe7b821ccb1f81424bb90d354efc361f1c6d0af	20-Mar-26 OSDE 000062938930501 008621 188.780,44	f
469	11	1	2026-03-20	BONIF. CONSUMO CABIFY2612UYZHOPPT	004016	refund	ARS	-4001.94	\N	\N	committed	11:0ea7f8c0e11171f7284c5b1007c3bb43231e0bd16c68e4cd316bdf5821b03f95	20-Mar-26 BONIF. CONSUMO CABIFY2612UYZHOPPT 004016 -4.001,94	f
470	11	1	2026-03-21	MERPAGO*CMORRES	056314	payment	ARS	95088.60	2	20	committed	11:adeaa7eb2b382fa5a59524d173c0217697062cd18b6dd0adef4a5449bc128123	21-Mar-26 MERPAGO*CMORRES 056314 95.088,60	f
442	11	1	2026-03-03	SU PAGO EN PESOS	\N	previous_payment	ARS	-1967432.74	\N	\N	ignored	11:26ddc980188ba1c8c8cdf2770e3fbabc3b2a2581b63579e03da5df522617dae3	03-Mar-26 SU PAGO EN PESOS -1.967.432,74	f
580	14	1	2026-06-11	TITULOS 023130227802CUT Nro:00000011	\N	income	ARS	1365978.61	3	\N	pending	14:70e3b3f69b97dbebc084acc15edafb9c	11/06/2026 | TITULOS 023130227802CUT Nro:00000011 | 316 - CATALINAS | 1.365.978,61 | 1.378.658,73	t
581	14	1	2026-06-11	TITULOS 023130211303CUT Nro:00000011	\N	debit_purchase	ARS	-7569.88	3	\N	pending	14:fc8cf39aa573e962d00e15d857ad862c	11/06/2026 | TITULOS 023130211303CUT Nro:00000011 | 316 - CATALINAS | -7.569,88 | 12.680,12	t
583	14	1	2026-06-11	Cambio de moneda extranjera	\N	income	ARS	70250.00	\N	\N	pending	14:8dc34a9cc50eadd949d30961e9b7120a	11/06/2026 | Cambio de moneda extranjera | 100 - BANCA ONLINE | 70.250,00 | 70.250,00	f
590	14	1	2026-06-05	TITULOS 023117412102CUT Nro:00000011	\N	income	ARS	1448335.49	3	\N	pending	14:da316f54681233ac20e1f04d299ddbb3	05/06/2026 | TITULOS 023117412102CUT Nro:00000011 | 316 - CATALINAS | 1.448.335,49 | 1.599.102,67	t
591	14	1	2026-06-05	TITULOS 023117383903CUT Nro:00000011	\N	debit_purchase	ARS	-7983.95	3	\N	pending	14:c5e0a388dcaef5489678edd660342ffe	05/06/2026 | TITULOS 023117383903CUT Nro:00000011 | 316 - CATALINAS | -7.983,95 | 150.767,18	t
600	14	1	2026-05-05	TITULOS 023056002002CUT Nro:00000011	\N	income	ARS	4962817.02	3	\N	pending	14:043f291693b61ed051e1a47cb2214da5	05/05/2026 | TITULOS 023056002002CUT Nro:00000011 | 316 - CATALINAS | 4.962.817,02 | 5.151.896,25	t
569	14	1	2026-07-02	TRANSFERENCIA	\N	transfer	ARS	-119500.00	\N	\N	committed	14:0a22e8ba4fc0f3cfbbc03e2b9aa16628	02/07/2026 | TRANSFERENCIA | 100 - BANCA ONLINE | -119.500,00 | 999.607,00	f
196	6	1	2026-04-09	CR.RG 5617 30% M	\N	tax	ARS	-6194.61	4	\N	committed	6:6ddf616443f40968143dfd4478d9c886886139472c76d8a6b0d160dd22df19e5	09-Abr-26 CR.RG 5617 30% M -6.194,61 3-91300005-03 .orN TIUC otpircsnI elbasnopseR AVI - .A.S anitnegrA AVBB ocnaB	f
197	6	1	2026-04-08	IGUAZU ARGENTINA SA	000476	purchase	ARS	190000.00	\N	\N	committed	6:f604ccdeacbfcdf4321cc845d8fecb38e9d306c85987feeffa6f54bd67e15143	08-Abr-26 IGUAZU ARGENTINA SA 000476 190.000,00	f
198	6	1	2026-04-14	MERPAGO*HERTZARG	171149	payment	ARS	463247.64	\N	\N	committed	6:38bd117b39ae6895583976efdbba9cb62b11d5062be456b8884d601aeadd6663	14-Abr-26 MERPAGO*HERTZARG 171149 463.247,64	f
199	6	1	2026-04-30	MERPAGO*MERCADOLIBRE C.05/06	821025	payment	ARS	9998.33	\N	\N	committed	6:e0c3c8bcf9163eac2ea9fa8078c50524210b368c32aa0f333babc1655f1536cf	03-Dic-25 MERPAGO*MERCADOLIBRE C.05/06 821025 9.998,33	f
200	6	1	2026-04-30	MERPAGO*KAMADOARGENTI C.03/03	826550	payment	ARS	14412.33	\N	\N	committed	6:f0e0f74548e35fc53bd845fc71b8acffb4972e87418e30833afc3b597851454d	30-Ene-26 MERPAGO*KAMADOARGENTI C.03/03 826550 14.412,33	f
201	6	1	2026-04-30	MERPAGO*KAMADOARGENTI C.03/06	260104	payment	ARS	31083.50	\N	\N	committed	6:3c534fb0b963126cd2474db4207f526e41b214a2285e05367b05adc4018e4ba2	04-Feb-26 MERPAGO*KAMADOARGENTI C.03/06 260104 31.083,50	f
601	14	1	2026-05-05	TITULOS 023055977503CUT Nro:00000011	\N	debit_purchase	ARS	-27033.47	3	\N	pending	14:c4bf06b187690efc2a46a652da748a2a	05/05/2026 | TITULOS 023055977503CUT Nro:00000011 | 316 - CATALINAS | -27.033,47 | 189.079,23	t
610	14	1	2026-04-21	TITULOS 023032368202CUT Nro:00000011	\N	income	ARS	1405186.64	3	\N	pending	14:cb7506d0c025101c7d2ca7fe69a0f791	21/04/2026 | TITULOS 023032368202CUT Nro:00000011 | 316 - CATALINAS | 1.405.186,64 | 1.732.335,75	t
611	14	1	2026-04-21	TITULOS 023032355403CUT Nro:00000011	\N	debit_purchase	ARS	-7615.48	3	\N	pending	14:562f5df91758ef31ff833ee350d83df7	21/04/2026 | TITULOS 023032355403CUT Nro:00000011 | 316 - CATALINAS | -7.615,48 | 327.149,11	t
621	14	1	2026-04-08	TITULOS 023006978102CUT Nro:00000011	\N	income	ARS	2551479.66	3	\N	pending	14:a09cf0169676fd30da3bebaa54f7d665	08/04/2026 | TITULOS 023006978102CUT Nro:00000011 | 316 - CATALINAS | 2.551.479,66 | 2.790.602,16	t
622	14	1	2026-04-08	TITULOS 023006955803CUT Nro:00000011	\N	debit_purchase	ARS	-13935.78	3	\N	pending	14:9e66861c18003b4c6eeee0e08015f492	08/04/2026 | TITULOS 023006955803CUT Nro:00000011 | 316 - CATALINAS | -13.935,78 | 239.122,50	t
638	14	1	2026-03-02	TITULOS 022938943502CUT Nro:00000011	\N	income	ARS	1982195.38	3	\N	pending	14:14165bf90fd992e0d755b755a96196e6	02/03/2026 | TITULOS 022938943502CUT Nro:00000011 | 316 - CATALINAS | 1.982.195,38 | 2.972.216,53	t
639	14	1	2026-03-02	TITULOS 022938914403CUT Nro:00000011	\N	debit_purchase	ARS	-10931.74	3	\N	pending	14:af422e1ec5f8e23780037369521ae51e	02/03/2026 | TITULOS 022938914403CUT Nro:00000011 | 316 - CATALINAS | -10.931,74 | 990.021,15	t
641	14	1	2026-02-23	OPERACION EN EFECTIVO TARJE 18073039 OP5056	\N	debit_purchase	ARS	-400000.00	\N	\N	pending	14:549f06c44143dd40d8d0016fe3cfc1fe	23/02/2026 | OPERACION EN EFECTIVO TARJE 18073039 OP5056 | 167 - ADROGUE | -400.000,00 | 1.000.928,98	f
643	14	1	2026-02-20	TITULOS 022922470102CUT Nro:00000011	\N	income	ARS	1394661.87	3	\N	pending	14:656e97775029742d803d217e7982b15e	20/02/2026 | TITULOS 022922470102CUT Nro:00000011 | 316 - CATALINAS | 1.394.661,87 | 1.595.229,30	t
644	14	1	2026-02-20	TITULOS 022922451903CUT Nro:00000011	\N	debit_purchase	ARS	-7721.36	3	\N	pending	14:13933ee5e633e627987da1107187299d	20/02/2026 | TITULOS 022922451903CUT Nro:00000011 | 316 - CATALINAS | -7.721,36 | 200.567,43	t
223	6	1	2026-04-16	DISCO SM 037	176047	purchase	ARS	95440.00	2	\N	committed	6:a5ef11903da77edbdb0de7715dfc535807804cf23a625fbc95d164c7490baa59	16-Abr-26 DISCO SM 037 176047 95.440,00	f
224	6	1	2026-04-16	PEDIDOSYA*PERTUTTI ADRO	007972	purchase	ARS	40580.00	1	\N	committed	6:ef128850d1918d678daa9946c7da200bbd2c8aaa1ca5a4fc3e713a75abdd53a0	16-Abr-26 PEDIDOSYA*PERTUTTI ADRO 007972 40.580,00	f
225	6	1	2026-04-17	CLARO DEB AUT 000021326330519	000001	purchase	ARS	26039.76	3	5	committed	6:e2c52496174184b63eb545d5315a3dcde7498971f083ba458bf98c9da8c08042	17-Abr-26 CLARO DEB AUT 000021326330519 000001 26.039,76	t
226	6	1	2026-04-17	PEDIDOSYA*TIENDA DE CAF	008017	purchase	ARS	21430.00	1	\N	committed	6:14ee56b6b90459e20456c701cfbd5285282d0dfdf99d02b8af9bc981f05c26cf	17-Abr-26 PEDIDOSYA*TIENDA DE CAF 008017 21.430,00	f
227	6	1	2026-04-17	AMAZON PRIME*DU0 18CsiyApr	992603	purchase	USD	14.99	8	\N	committed	6:55bcedbd6103f956844b6688d868edb26d7b8e77da95942978063161155d0cd9	17-Abr-26 AMAZON PRIME*DU0 18CsiyAprUSD 14,99 992603 14,99	t
228	6	1	2026-04-19	STEAMGAMES.COM 4259522985	044321	purchase	USD	8.99	11	\N	committed	6:937a30853874142a18296b7e19d02fbda220f5b269c4e08204ffea8d710fd976	19-Abr-26 STEAMGAMES.COM 4259522985 USD 8,99 044321 8,99	f
229	6	1	2026-04-20	METROGAS SA DEB 020307417400	685687	purchase	ARS	42313.52	3	3	committed	6:abf3e3e87b2cb2851af85a00c1e7fa9464f8380d883718e59f2ed483fd851402	20-Abr-26 METROGAS SA DEB 020307417400 685687 42.313,52	t
230	6	1	2026-04-21	CAJA SEG-PROMO BB023838068 -0	000001	purchase	ARS	201755.00	7	7	committed	6:1e3d01134a2b02b6175384debeb7acfea93efcb862fef93eb61babd311f82ac0	21-Abr-26 CAJA SEG-PROMO BB023838068 -0 000001 201.755,00	t
\.


--
-- Data for Name: memberships; Type: TABLE DATA; Schema: public; Owner: spent
--

COPY public.memberships (id, user_id, home_group_id, role) FROM stdin;
1	1	1	owner
2	2	1	member
\.


--
-- Data for Name: merchants; Type: TABLE DATA; Schema: public; Owner: spent
--

COPY public.merchants (id, home_group_id, display_name, normalized_name, category_id, subcategory_id, is_recurring) FROM stdin;
1	1	CR.RG 5617 30% M	CR.RG 5617 30% M	4	\N	f
2	1	IGUAZU ARGENTINA SA	IGUAZU ARGENTINA SA	9	\N	f
3	1	MERPAGO*HERTZARG	MERPAGO*HERTZARG	9	\N	f
71	1	PAYU*AR*UBER	PAYU*AR*UBER	11	34	f
8	1	DLO*PEDIDOSYA PROPINA	DLO*PEDIDOSYA PROPINA	1	\N	f
9	1	PEDIDOSYA*TEQUESUR	PEDIDOSYA*TEQUESUR	1	\N	f
10	1	PEDIDOSYA*KFC ADROGUE	PEDIDOSYA*KFC ADROGUE	1	\N	f
11	1	MERPAGO*PELONLINE	MERPAGO*PELONLINE	2	13	f
39	1	COMISION CTA PWORLD	COMISION CTA PWORLD	3	\N	f
12	1	MERPAGO*PARQUEGAS	MERPAGO*PARQUEGAS	2	14	f
13	1	DLO*PEDIDOSYA PLUS	DLO*PEDIDOSYA PLUS	1	\N	f
14	1	MERPAGO*CMORRES	MERPAGO*CMORRES	2	20	f
15	1	DISCO SM 037 MODO	DISCO SM 037 MODO	2	\N	f
16	1	MOVISTAR HOGAR 000000568729017	MOVISTAR HOGAR 000000568729017	3	5	t
17	1	WL *Steam Purchase	WL *STEAM PURCHASE	11	33	f
18	1	DIA TIENDA 5556	DIA TIENDA 5556	2	10	f
19	1	Crunchyroll LLC	CRUNCHYROLL LLC	8	\N	f
20	1	PEDIDOSYA*DER GRUND TEM	PEDIDOSYA*DER GRUND TEM	1	\N	f
21	1	MERPAGO*TCTIENDAS	MERPAGO*TCTIENDAS	2	14	f
22	1	SHELL	SHELL	7	32	f
23	1	DISCO SM 037	DISCO SM 037	2	\N	f
24	1	PEDIDOSYA*PERTUTTI ADRO	PEDIDOSYA*PERTUTTI ADRO	1	\N	f
25	1	CLARO DEB AUT 000021326330519	CLARO DEB AUT 000021326330519	3	5	t
26	1	PEDIDOSYA*TIENDA DE CAF	PEDIDOSYA*TIENDA DE CAF	1	\N	f
27	1	AMAZON PRIME*DU0 18CsiyApr	AMAZON PRIME*DU0 18CSIYAPR	8	\N	t
28	1	STEAMGAMES.COM 4259522985	STEAMGAMES.COM 4259522985	11	33	f
29	1	METROGAS SA DEB 020307417400	METROGAS SA DEB 020307417400	3	3	t
30	1	CAJA SEG-PROMO BB023838068 -0	CAJA SEG-PROMO BB023838068 -0	7	7	t
31	1	PEDIDOSYA*CUQUET HOUSE	PEDIDOSYA*CUQUET HOUSE	1	\N	f
32	1	PEDIDOSYA*THOUSAND BURG	PEDIDOSYA*THOUSAND BURG	1	\N	f
33	1	STARBUCKS PORTAL LOMAS	STARBUCKS PORTAL LOMAS	11	34	f
34	1	OSDE 000062938930501	OSDE 000062938930501	6	\N	f
35	1	EDESUR	EDESUR	3	1	t
36	1	PEDIDOSYA*LAS MEDIALUNA	PEDIDOSYA*LAS MEDIALUNA	1	\N	f
37	1	HOTEL CATARATAS SA	HOTEL CATARATAS SA	9	\N	f
38	1	FOOD PATAGONIA SA	FOOD PATAGONIA SA	9	\N	f
40	1	DB IVA $ 21% 61.157,02	DB IVA $ 21% 61.157,02	4	\N	f
41	1	IIBB PERCEP-CABA 2,00%( 33368,17)	IIBB PERCEP-CABA 2,00%( 33368,17)	4	\N	f
42	1	IVA RG 4240 21%( 33368,17)	IVA RG 4240 21%( 33368,17)	4	\N	f
43	1	DB.RG 5617 30% ( 20858,58 )	DB.RG 5617 30% ( 20858,58 )	4	\N	f
44	1	CR IVA $ 21 %	CR IVA $ 21 %	4	\N	f
75	1	PAGO DE SERVICIOS TARJETA 18073039 OP3802	PAGO DE SERVICIOS TARJETA 18073039 OP3802	3	\N	t
45	1	ACA PUERTO IGUAZU COMB	ACA PUERTO IGUAZU COMB	10	\N	f
46	1	PEDIDOSYA*DIA ADROGUA I	PEDIDOSYA*DIA ADROGUA I	1	\N	f
47	1	PEDIDOSYA*CARREFOUR HIP	PEDIDOSYA*CARREFOUR HIP	1	\N	f
48	1	PEDIDOSYA*EXTRA	PEDIDOSYA*EXTRA	1	\N	f
49	1	OPENAI *CHATGPT SUBSCR	OPENAI *CHATGPT SUBSCR	8	\N	t
50	1	MERPAGO*WALDENCASES C.01/03	MERPAGO*WALDENCASES	11	\N	f
51	1	AMAZON PRIME*TT9 f9vrF5l8d	AMAZON PRIME*TT9 F9VRF5L8D	8	\N	t
52	1	STEAMGAMES.COM 4 425952298	STEAMGAMES.COM 4 425952298	11	\N	f
53	1	MERPAGO*LUVIKSA	MERPAGO*LUVIKSA	2	10	f
54	1	PEDIDOSYA*GLORIOSO CHUR	PEDIDOSYA*GLORIOSO CHUR	1	\N	f
55	1	DB IVA $ 21% 57.599,07	DB IVA $ 21% 57.599,07	4	\N	f
56	1	IIBB PERCEP-CABA 2,00%( 33871,75)	IIBB PERCEP-CABA 2,00%( 33871,75)	4	\N	f
57	1	IIBB PERCEP-CABA 2,00%( 36174,12)	IIBB PERCEP-CABA 2,00%( 36174,12)	4	\N	f
58	1	IVA RG 4240 21%( 33871,75)	IVA RG 4240 21%( 33871,75)	4	\N	f
59	1	IVA RG 4240 21%( 36174,12)	IVA RG 4240 21%( 36174,12)	4	\N	f
60	1	DB.RG 5617 30% ( 49423,37 )	DB.RG 5617 30% ( 49423,37 )	4	\N	f
61	1	DEV COMISION CTA PWORLD	DEV COMISION CTA PWORLD	3	\N	t
77	1	PAGO DE SERVICIOS TARJETA 18073039 OP9422	PAGO DE SERVICIOS TARJETA 18073039 OP9422	3	\N	t
5	1	MERPAGO*KAMADOARGENTI C.02/06	MERPAGO*KAMADOARGENTI	2	14	f
6	1	MERPAGO*SOHODENIMROPA C.02/03	MERPAGO*SOHODENIMROPA	14	\N	f
7	1	MERPAGO*ACIUM C.02/03	MERPAGO*ACIUM	13	\N	f
62	1	MERPAGO*TADA	MERPAGO*TADA	2	22	f
63	1	PEDIDOSYA*HARRYS KILLER	PEDIDOSYA*HARRYS KILLER	1	\N	f
64	1	PEDIDOSYA*FABRIC SUSHI	PEDIDOSYA*FABRIC SUSHI	1	\N	f
65	1	MERPAGO*DOGCENTER	MERPAGO*DOGCENTER	17	27	f
66	1	PEDIDOSYA*JIRO SUSHI AD	PEDIDOSYA*JIRO SUSHI AD	1	\N	f
67	1	AMAZON PRIME*BJ8 1iWVOeHn2	AMAZON PRIME*BJ8 1IWVOEHN2	8	\N	t
4	1	MERPAGO*MERCADOLIBRE	MERPAGO*MERCADOLIBRE	11	\N	f
68	1	CABIFY2612UYZHOPPT	CABIFY2612UYZHOPPT	10	\N	f
69	1	BONIF. CONSUMO CABIFY2612UYZHOPPT	BONIF. CONSUMO CABIFY2612UYZHOPPT	11	34	f
70	1	VICTORIA BROWN	VICTORIA BROWN	11	34	f
72	1	IIBB PERCEP-CABA 2,00%( 20648,72)	IIBB PERCEP-CABA 2,00%( 20648,72)	4	\N	f
73	1	IVA RG 4240 21%( 20648,72)	IVA RG 4240 21%( 20648,72)	4	\N	f
74	1	DB.RG 5617 30% ( 20648,72 )	DB.RG 5617 30% ( 20648,72 )	4	\N	f
78	1	PAGO DE SERVICIOS TARJETA 18073039 OP2788	PAGO DE SERVICIOS TARJETA 18073039 OP2788	3	\N	t
79	1	PAGO DE SERVICIOS TARJETA 18073039 OP5446	PAGO DE SERVICIOS TARJETA 18073039 OP5446	3	\N	t
80	1	TRANSFERENCIA CCP316 316621 5 Nro:00010008	TRANSFERENCIA CCP316 316621 5 NRO:00010008	13	\N	f
81	1	PAGO CON VISA DEBITO 18073039 OP4102	PAGO CON VISA DEBITO 18073039 OP4102	3	1	t
82	1	PAGO DE SERVICIOS TARJETA 18073039 OP8518	PAGO DE SERVICIOS TARJETA 18073039 OP8518	3	\N	t
83	1	PAGO DE SERVICIOS TARJETA 18073039 OP8363	PAGO DE SERVICIOS TARJETA 18073039 OP8363	3	\N	t
84	1	TRANSFERENCIA CAP027 027024 8 Nro:00010008	TRANSFERENCIA CAP027 027024 8 NRO:00010008	11	\N	f
85	1	Transferencia inmediata	TRANSFERENCIA INMEDIATA	13	\N	f
86	1	PAGO DE SERVICIOS TARJETA 18073039 OP1619	PAGO DE SERVICIOS TARJETA 18073039 OP1619	3	\N	t
87	1	PAGO DE SERVICIOS TARJETA 18073039 OP5935	PAGO DE SERVICIOS TARJETA 18073039 OP5935	3	\N	t
88	1	DEBITO DIRECTO	DEBITO DIRECTO	4	\N	f
89	1	PAGO DE SERVICIOS TARJETA 18073039 OP8708	PAGO DE SERVICIOS TARJETA 18073039 OP8708	3	\N	t
90	1	PAGO DE SERVICIOS TARJETA 18073039 OP3682	PAGO DE SERVICIOS TARJETA 18073039 OP3682	3	\N	t
91	1	PAGO DE SERVICIOS TARJETA 18073039 OP7422	PAGO DE SERVICIOS TARJETA 18073039 OP7422	3	\N	t
92	1	PAGO DE SERVICIOS TARJETA 18073039 OP9027	PAGO DE SERVICIOS TARJETA 18073039 OP9027	3	\N	t
93	1	PAGO DE SERVICIOS TARJETA 18073039 OP3266	PAGO DE SERVICIOS TARJETA 18073039 OP3266	3	\N	t
94	1	PAGO DE SERVICIOS TARJETA 18073039 OP1997	PAGO DE SERVICIOS TARJETA 18073039 OP1997	3	\N	t
95	1	PAGO DE SERVICIOS TARJETA 18073039 OP3086	PAGO DE SERVICIOS TARJETA 18073039 OP3086	3	\N	t
76	1	TRANSFERENCIA	TRANSFERENCIA	13	\N	f
96	1	PAGO DE SERVICIOS TARJETA 18073039 OP6471	PAGO DE SERVICIOS TARJETA 18073039 OP6471	3	\N	t
97	1	PAGO DE SERVICIOS TARJETA 18073039 OP1526	PAGO DE SERVICIOS TARJETA 18073039 OP1526	3	\N	t
98	1	PAGO DE SERVICIOS TARJETA 18073039 OP3417	PAGO DE SERVICIOS TARJETA 18073039 OP3417	3	\N	t
\.


--
-- Data for Name: receipt_imports; Type: TABLE DATA; Schema: public; Owner: spent
--

COPY public.receipt_imports (id, home_group_id, uploaded_by_user_id, expense_id, filename, status, raw_text, created_at, category_id) FROM stdin;
\.


--
-- Data for Name: receipt_items; Type: TABLE DATA; Schema: public; Owner: spent
--

COPY public.receipt_items (id, receipt_import_id, description, quantity, unit_price, total_amount, status, subcategory_id, suggested_subcategory_name) FROM stdin;
\.


--
-- Data for Name: recurring_rules; Type: TABLE DATA; Schema: public; Owner: spent
--

COPY public.recurring_rules (id, home_group_id, description_pattern, category_id, currency, expected_amount, cadence, active) FROM stdin;
6	1	AMAZON PRIME*DU0 18CSIYAPR	8	USD	14.99	monthly	t
8	1	OPENAI *CHATGPT SUBSCR	8	USD	20.00	monthly	t
9	1	AMAZON PRIME*TT9 F9VRF5L8D	8	USD	14.99	monthly	t
10	1	DEV COMISION CTA PWORLD	3	ARS	-57599.07	monthly	t
1	1	MOVISTAR HOGAR	3	ARS	44860.00	monthly	t
2	1	CLARO DEB AUT	3	ARS	25066.26	monthly	t
4	1	EDESUR	3	ARS	127135.77	monthly	t
5	1	CAJA SEG-PROMO BB023838068 -0	7	ARS	196226.00	monthly	t
11	1	AMAZON PRIME*BJ8 1IWVOEHN2	8	USD	14.99	monthly	t
3	1	METROGAS SA DEB	3	ARS	37275.45	monthly	t
7	1	COMISION CTA PWORLD	3	ARS	57599.07	monthly	f
12	1	PAGO DE SERVICIOS TARJETA OP3802	3	ARS	-38579.44	monthly	t
13	1	PAGO DE SERVICIOS TARJETA OP9422	3	ARS	-38362.49	monthly	t
14	1	PAGO DE SERVICIOS TARJETA OP2788	3	ARS	-37827.74	monthly	t
15	1	PAGO DE SERVICIOS TARJETA OP5446	3	ARS	-16580.10	monthly	t
16	1	PAGO CON VISA DEBITO OP4102	3	ARS	-349850.36	monthly	t
17	1	PAGO DE SERVICIOS TARJETA OP8518	3	ARS	-36539.04	monthly	t
18	1	PAGO DE SERVICIOS TARJETA OP8363	3	ARS	-16187.00	monthly	t
19	1	PAGO DE SERVICIOS TARJETA OP1619	3	ARS	-36539.04	monthly	t
20	1	PAGO DE SERVICIOS TARJETA OP5935	3	ARS	-15703.10	monthly	t
22	1	PAGO DE SERVICIOS TARJETA OP8708	3	ARS	-35946.61	monthly	t
23	1	PAGO DE SERVICIOS TARJETA OP3682	3	ARS	-33132.40	monthly	t
24	1	PAGO DE SERVICIOS TARJETA OP7422	3	ARS	-32332.42	monthly	t
25	1	PAGO DE SERVICIOS TARJETA OP9027	3	ARS	-15331.30	monthly	t
21	1	TRANSFERENCIA	3	ARS	-100000.00	monthly	f
26	1	PAGO DE SERVICIOS TARJETA OP3266	3	ARS	-32332.42	monthly	t
27	1	PAGO DE SERVICIOS TARJETA OP1997	3	ARS	-31814.94	monthly	t
28	1	PAGO DE SERVICIOS TARJETA OP3086	3	ARS	-14938.20	monthly	t
29	1	PAGO DE SERVICIOS TARJETA OP6471	3	ARS	-32979.07	monthly	t
30	1	PAGO DE SERVICIOS TARJETA OP1526	3	ARS	-31427.40	monthly	t
31	1	PAGO DE SERVICIOS TARJETA OP3417	3	ARS	-30591.26	monthly	t
\.


--
-- Data for Name: subcategories; Type: TABLE DATA; Schema: public; Owner: spent
--

COPY public.subcategories (id, home_group_id, category_id, name, is_system) FROM stdin;
1	1	3	Electricidad	t
2	1	3	Agua	t
3	1	3	Gas	t
4	1	3	Auto	t
5	1	3	Internet	t
6	1	3	Seguro	t
7	1	7	Seguro	t
8	1	7	Mantenimiento	t
9	1	7	Patente	t
10	1	2	Almacén	f
11	1	2	Descuentos	f
12	1	2	Panadería	f
13	1	2	Perfumería y Cuidado Personal	f
14	1	2	Bazar y Hogar	f
15	1	2	Limpieza	f
16	1	2	Farmacia y Perfumería	f
17	1	2	Frutas y Verduras	f
19	1	2	Verdulería	t
20	1	2	Carnicería	t
22	1	2	Bebida alcholica	f
23	1	2	Pileta	f
24	1	2	Repuestos	f
25	1	2	Electrodomestico	f
26	1	3	Banco	f
27	1	17	Alimento	f
28	1	17	Piedras	f
29	1	17	Veterinaria	f
30	1	17	Juguetes	f
31	1	17	Otros	f
32	1	7	Combustible	f
33	1	11	Juego  PC	f
34	1	11	Salida	f
35	1	11	Libro	f
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: spent
--

COPY public.users (id, email, display_name, google_sub, created_at) FROM stdin;
1	mauro@example.test	Mauro	\N	2026-07-06 00:36:45.967014
2	mica@example.test	Mica	\N	2026-07-06 00:36:45.968444
\.


--
-- Name: audit_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: spent
--

SELECT pg_catalog.setval('public.audit_logs_id_seq', 57, true);


--
-- Name: cash_wallet_entries_id_seq; Type: SEQUENCE SET; Schema: public; Owner: spent
--

SELECT pg_catalog.setval('public.cash_wallet_entries_id_seq', 1, false);


--
-- Name: categories_id_seq; Type: SEQUENCE SET; Schema: public; Owner: spent
--

SELECT pg_catalog.setval('public.categories_id_seq', 17, true);


--
-- Name: earnings_id_seq; Type: SEQUENCE SET; Schema: public; Owner: spent
--

SELECT pg_catalog.setval('public.earnings_id_seq', 20, true);


--
-- Name: expenses_id_seq; Type: SEQUENCE SET; Schema: public; Owner: spent
--

SELECT pg_catalog.setval('public.expenses_id_seq', 227, true);


--
-- Name: fx_rates_id_seq; Type: SEQUENCE SET; Schema: public; Owner: spent
--

SELECT pg_catalog.setval('public.fx_rates_id_seq', 1, true);


--
-- Name: home_groups_id_seq; Type: SEQUENCE SET; Schema: public; Owner: spent
--

SELECT pg_catalog.setval('public.home_groups_id_seq', 1, true);


--
-- Name: import_batches_id_seq; Type: SEQUENCE SET; Schema: public; Owner: spent
--

SELECT pg_catalog.setval('public.import_batches_id_seq', 14, true);


--
-- Name: import_lines_id_seq; Type: SEQUENCE SET; Schema: public; Owner: spent
--

SELECT pg_catalog.setval('public.import_lines_id_seq', 653, true);


--
-- Name: memberships_id_seq; Type: SEQUENCE SET; Schema: public; Owner: spent
--

SELECT pg_catalog.setval('public.memberships_id_seq', 2, true);


--
-- Name: merchants_id_seq; Type: SEQUENCE SET; Schema: public; Owner: spent
--

SELECT pg_catalog.setval('public.merchants_id_seq', 98, true);


--
-- Name: receipt_imports_id_seq; Type: SEQUENCE SET; Schema: public; Owner: spent
--

SELECT pg_catalog.setval('public.receipt_imports_id_seq', 1, false);


--
-- Name: receipt_items_id_seq; Type: SEQUENCE SET; Schema: public; Owner: spent
--

SELECT pg_catalog.setval('public.receipt_items_id_seq', 1, false);


--
-- Name: recurring_rules_id_seq; Type: SEQUENCE SET; Schema: public; Owner: spent
--

SELECT pg_catalog.setval('public.recurring_rules_id_seq', 31, true);


--
-- Name: subcategories_id_seq; Type: SEQUENCE SET; Schema: public; Owner: spent
--

SELECT pg_catalog.setval('public.subcategories_id_seq', 35, true);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: spent
--

SELECT pg_catalog.setval('public.users_id_seq', 2, true);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: cash_wallet_entries cash_wallet_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.cash_wallet_entries
    ADD CONSTRAINT cash_wallet_entries_pkey PRIMARY KEY (id);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);


--
-- Name: earnings earnings_pkey; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.earnings
    ADD CONSTRAINT earnings_pkey PRIMARY KEY (id);


--
-- Name: expenses expenses_pkey; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.expenses
    ADD CONSTRAINT expenses_pkey PRIMARY KEY (id);


--
-- Name: fx_rates fx_rates_pkey; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.fx_rates
    ADD CONSTRAINT fx_rates_pkey PRIMARY KEY (id);


--
-- Name: home_groups home_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.home_groups
    ADD CONSTRAINT home_groups_pkey PRIMARY KEY (id);


--
-- Name: import_batches import_batches_pkey; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.import_batches
    ADD CONSTRAINT import_batches_pkey PRIMARY KEY (id);


--
-- Name: import_lines import_lines_pkey; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.import_lines
    ADD CONSTRAINT import_lines_pkey PRIMARY KEY (id);


--
-- Name: memberships memberships_pkey; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.memberships
    ADD CONSTRAINT memberships_pkey PRIMARY KEY (id);


--
-- Name: merchants merchants_pkey; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.merchants
    ADD CONSTRAINT merchants_pkey PRIMARY KEY (id);


--
-- Name: receipt_imports receipt_imports_pkey; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.receipt_imports
    ADD CONSTRAINT receipt_imports_pkey PRIMARY KEY (id);


--
-- Name: receipt_items receipt_items_pkey; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.receipt_items
    ADD CONSTRAINT receipt_items_pkey PRIMARY KEY (id);


--
-- Name: recurring_rules recurring_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.recurring_rules
    ADD CONSTRAINT recurring_rules_pkey PRIMARY KEY (id);


--
-- Name: subcategories subcategories_pkey; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.subcategories
    ADD CONSTRAINT subcategories_pkey PRIMARY KEY (id);


--
-- Name: categories uq_category_home_name; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT uq_category_home_name UNIQUE (home_group_id, name);


--
-- Name: fx_rates uq_fx_rate; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.fx_rates
    ADD CONSTRAINT uq_fx_rate UNIQUE (date, source, from_currency, to_currency);


--
-- Name: import_lines uq_import_line_fingerprint; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.import_lines
    ADD CONSTRAINT uq_import_line_fingerprint UNIQUE (home_group_id, fingerprint);


--
-- Name: memberships uq_membership_user_home; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.memberships
    ADD CONSTRAINT uq_membership_user_home UNIQUE (user_id, home_group_id);


--
-- Name: merchants uq_merchant_home_name; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.merchants
    ADD CONSTRAINT uq_merchant_home_name UNIQUE (home_group_id, normalized_name);


--
-- Name: subcategories uq_subcategory_category_name; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.subcategories
    ADD CONSTRAINT uq_subcategory_category_name UNIQUE (category_id, name);


--
-- Name: users users_google_sub_key; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_google_sub_key UNIQUE (google_sub);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_audit_logs_action; Type: INDEX; Schema: public; Owner: spent
--

CREATE INDEX ix_audit_logs_action ON public.audit_logs USING btree (action);


--
-- Name: ix_audit_logs_created_at; Type: INDEX; Schema: public; Owner: spent
--

CREATE INDEX ix_audit_logs_created_at ON public.audit_logs USING btree (created_at);


--
-- Name: ix_audit_logs_home_group_id; Type: INDEX; Schema: public; Owner: spent
--

CREATE INDEX ix_audit_logs_home_group_id ON public.audit_logs USING btree (home_group_id);


--
-- Name: ix_cash_wallet_entries_home_group_id; Type: INDEX; Schema: public; Owner: spent
--

CREATE INDEX ix_cash_wallet_entries_home_group_id ON public.cash_wallet_entries USING btree (home_group_id);


--
-- Name: ix_earnings_date; Type: INDEX; Schema: public; Owner: spent
--

CREATE INDEX ix_earnings_date ON public.earnings USING btree (date);


--
-- Name: ix_earnings_home_group_id; Type: INDEX; Schema: public; Owner: spent
--

CREATE INDEX ix_earnings_home_group_id ON public.earnings USING btree (home_group_id);


--
-- Name: ix_expenses_date; Type: INDEX; Schema: public; Owner: spent
--

CREATE INDEX ix_expenses_date ON public.expenses USING btree (date);


--
-- Name: ix_expenses_home_group_id; Type: INDEX; Schema: public; Owner: spent
--

CREATE INDEX ix_expenses_home_group_id ON public.expenses USING btree (home_group_id);


--
-- Name: ix_fx_rates_date; Type: INDEX; Schema: public; Owner: spent
--

CREATE INDEX ix_fx_rates_date ON public.fx_rates USING btree (date);


--
-- Name: ix_import_batches_home_group_id; Type: INDEX; Schema: public; Owner: spent
--

CREATE INDEX ix_import_batches_home_group_id ON public.import_batches USING btree (home_group_id);


--
-- Name: ix_import_lines_home_group_id; Type: INDEX; Schema: public; Owner: spent
--

CREATE INDEX ix_import_lines_home_group_id ON public.import_lines USING btree (home_group_id);


--
-- Name: ix_receipt_imports_home_group_id; Type: INDEX; Schema: public; Owner: spent
--

CREATE INDEX ix_receipt_imports_home_group_id ON public.receipt_imports USING btree (home_group_id);


--
-- Name: ix_receipt_items_receipt_import_id; Type: INDEX; Schema: public; Owner: spent
--

CREATE INDEX ix_receipt_items_receipt_import_id ON public.receipt_items USING btree (receipt_import_id);


--
-- Name: ix_recurring_rules_home_group_id; Type: INDEX; Schema: public; Owner: spent
--

CREATE INDEX ix_recurring_rules_home_group_id ON public.recurring_rules USING btree (home_group_id);


--
-- Name: ix_subcategories_category_id; Type: INDEX; Schema: public; Owner: spent
--

CREATE INDEX ix_subcategories_category_id ON public.subcategories USING btree (category_id);


--
-- Name: ix_subcategories_home_group_id; Type: INDEX; Schema: public; Owner: spent
--

CREATE INDEX ix_subcategories_home_group_id ON public.subcategories USING btree (home_group_id);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: spent
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: audit_logs audit_logs_actor_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_actor_user_id_fkey FOREIGN KEY (actor_user_id) REFERENCES public.users(id);


--
-- Name: audit_logs audit_logs_home_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_home_group_id_fkey FOREIGN KEY (home_group_id) REFERENCES public.home_groups(id);


--
-- Name: cash_wallet_entries cash_wallet_entries_expense_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.cash_wallet_entries
    ADD CONSTRAINT cash_wallet_entries_expense_id_fkey FOREIGN KEY (expense_id) REFERENCES public.expenses(id);


--
-- Name: cash_wallet_entries cash_wallet_entries_home_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.cash_wallet_entries
    ADD CONSTRAINT cash_wallet_entries_home_group_id_fkey FOREIGN KEY (home_group_id) REFERENCES public.home_groups(id);


--
-- Name: cash_wallet_entries cash_wallet_entries_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.cash_wallet_entries
    ADD CONSTRAINT cash_wallet_entries_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: categories categories_home_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_home_group_id_fkey FOREIGN KEY (home_group_id) REFERENCES public.home_groups(id);


--
-- Name: earnings earnings_home_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.earnings
    ADD CONSTRAINT earnings_home_group_id_fkey FOREIGN KEY (home_group_id) REFERENCES public.home_groups(id);


--
-- Name: earnings earnings_import_line_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.earnings
    ADD CONSTRAINT earnings_import_line_id_fkey FOREIGN KEY (import_line_id) REFERENCES public.import_lines(id);


--
-- Name: earnings earnings_uploaded_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.earnings
    ADD CONSTRAINT earnings_uploaded_by_user_id_fkey FOREIGN KEY (uploaded_by_user_id) REFERENCES public.users(id);


--
-- Name: earnings earnings_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.earnings
    ADD CONSTRAINT earnings_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: expenses expenses_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.expenses
    ADD CONSTRAINT expenses_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: expenses expenses_home_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.expenses
    ADD CONSTRAINT expenses_home_group_id_fkey FOREIGN KEY (home_group_id) REFERENCES public.home_groups(id);


--
-- Name: expenses expenses_import_line_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.expenses
    ADD CONSTRAINT expenses_import_line_id_fkey FOREIGN KEY (import_line_id) REFERENCES public.import_lines(id);


--
-- Name: expenses expenses_paid_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.expenses
    ADD CONSTRAINT expenses_paid_by_user_id_fkey FOREIGN KEY (paid_by_user_id) REFERENCES public.users(id);


--
-- Name: expenses expenses_subcategory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.expenses
    ADD CONSTRAINT expenses_subcategory_id_fkey FOREIGN KEY (subcategory_id) REFERENCES public.subcategories(id);


--
-- Name: expenses expenses_uploaded_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.expenses
    ADD CONSTRAINT expenses_uploaded_by_user_id_fkey FOREIGN KEY (uploaded_by_user_id) REFERENCES public.users(id);


--
-- Name: import_batches import_batches_home_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.import_batches
    ADD CONSTRAINT import_batches_home_group_id_fkey FOREIGN KEY (home_group_id) REFERENCES public.home_groups(id);


--
-- Name: import_batches import_batches_uploaded_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.import_batches
    ADD CONSTRAINT import_batches_uploaded_by_user_id_fkey FOREIGN KEY (uploaded_by_user_id) REFERENCES public.users(id);


--
-- Name: import_lines import_lines_home_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.import_lines
    ADD CONSTRAINT import_lines_home_group_id_fkey FOREIGN KEY (home_group_id) REFERENCES public.home_groups(id);


--
-- Name: import_lines import_lines_import_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.import_lines
    ADD CONSTRAINT import_lines_import_batch_id_fkey FOREIGN KEY (import_batch_id) REFERENCES public.import_batches(id);


--
-- Name: import_lines import_lines_suggested_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.import_lines
    ADD CONSTRAINT import_lines_suggested_category_id_fkey FOREIGN KEY (suggested_category_id) REFERENCES public.categories(id);


--
-- Name: import_lines import_lines_suggested_subcategory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.import_lines
    ADD CONSTRAINT import_lines_suggested_subcategory_id_fkey FOREIGN KEY (suggested_subcategory_id) REFERENCES public.subcategories(id);


--
-- Name: memberships memberships_home_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.memberships
    ADD CONSTRAINT memberships_home_group_id_fkey FOREIGN KEY (home_group_id) REFERENCES public.home_groups(id);


--
-- Name: memberships memberships_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.memberships
    ADD CONSTRAINT memberships_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: merchants merchants_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.merchants
    ADD CONSTRAINT merchants_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: merchants merchants_home_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.merchants
    ADD CONSTRAINT merchants_home_group_id_fkey FOREIGN KEY (home_group_id) REFERENCES public.home_groups(id);


--
-- Name: merchants merchants_subcategory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.merchants
    ADD CONSTRAINT merchants_subcategory_id_fkey FOREIGN KEY (subcategory_id) REFERENCES public.subcategories(id);


--
-- Name: receipt_imports receipt_imports_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.receipt_imports
    ADD CONSTRAINT receipt_imports_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: receipt_imports receipt_imports_expense_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.receipt_imports
    ADD CONSTRAINT receipt_imports_expense_id_fkey FOREIGN KEY (expense_id) REFERENCES public.expenses(id);


--
-- Name: receipt_imports receipt_imports_home_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.receipt_imports
    ADD CONSTRAINT receipt_imports_home_group_id_fkey FOREIGN KEY (home_group_id) REFERENCES public.home_groups(id);


--
-- Name: receipt_imports receipt_imports_uploaded_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.receipt_imports
    ADD CONSTRAINT receipt_imports_uploaded_by_user_id_fkey FOREIGN KEY (uploaded_by_user_id) REFERENCES public.users(id);


--
-- Name: receipt_items receipt_items_receipt_import_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.receipt_items
    ADD CONSTRAINT receipt_items_receipt_import_id_fkey FOREIGN KEY (receipt_import_id) REFERENCES public.receipt_imports(id);


--
-- Name: receipt_items receipt_items_subcategory_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.receipt_items
    ADD CONSTRAINT receipt_items_subcategory_id_fkey FOREIGN KEY (subcategory_id) REFERENCES public.subcategories(id);


--
-- Name: recurring_rules recurring_rules_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.recurring_rules
    ADD CONSTRAINT recurring_rules_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: recurring_rules recurring_rules_home_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.recurring_rules
    ADD CONSTRAINT recurring_rules_home_group_id_fkey FOREIGN KEY (home_group_id) REFERENCES public.home_groups(id);


--
-- Name: subcategories subcategories_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.subcategories
    ADD CONSTRAINT subcategories_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: subcategories subcategories_home_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: spent
--

ALTER TABLE ONLY public.subcategories
    ADD CONSTRAINT subcategories_home_group_id_fkey FOREIGN KEY (home_group_id) REFERENCES public.home_groups(id);


--
-- PostgreSQL database dump complete
--

\unrestrict jdmnf5NNTAzIrPSnas5QW1bsaaRSAzaofoNBW8JkZgdRceAeWXaEJ3TihkdoBRe

