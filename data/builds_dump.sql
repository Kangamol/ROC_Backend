--
-- PostgreSQL database dump
--

\restrict gM7UQuaVvkMIfBbRWfAecQEpcaU04vYSMJcmsWflJnNrkl42QaszBO0bEDohbs5

-- Dumped from database version 16.15
-- Dumped by pg_dump version 16.15

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
-- Data for Name: CharacterBuild; Type: TABLE DATA; Schema: public; Owner: ro
--

INSERT INTO public."CharacterBuild" (id, "shareCode", title, "jobClass", "baseLevel", "jobLevel", str, agi, vit, "int", dex, luk, "createdAt", "updatedAt", "clothColor", gender, "hairColor", "hairStyle") VALUES ('4c9cd9e6-3a92-4321-ab6c-a1a302887814', '36e2b7b8', 'Test Knight', 'Knight', 99, 50, 90, 1, 80, 1, 40, 1, '2026-09-16 08:53:29.702', '2026-09-16 08:53:29.702', 0, 'M', 0, 1);
INSERT INTO public."CharacterBuild" (id, "shareCode", title, "jobClass", "baseLevel", "jobLevel", str, agi, vit, "int", dex, luk, "createdAt", "updatedAt", "clothColor", gender, "hairColor", "hairStyle") VALUES ('f6d5509a-dc32-405d-8912-0e314612aeed', '7577c098', 'My Build', 'Knight', 99, 50, 1, 1, 1, 1, 1, 1, '2026-09-16 09:09:42.688', '2026-09-16 09:09:42.688', 0, 'M', 0, 1);
INSERT INTO public."CharacterBuild" (id, "shareCode", title, "jobClass", "baseLevel", "jobLevel", str, agi, vit, "int", dex, luk, "createdAt", "updatedAt", "clothColor", gender, "hairColor", "hairStyle") VALUES ('908061bc-37ab-41e3-adcc-358b2b0fcbf8', '36d4ab79', 'My Build', 'Wizard', 99, 50, 1, 1, 1, 1, 1, 1, '2026-09-16 09:24:21.799', '2026-09-16 09:24:21.799', 2, 'F', 3, 5);


--
-- Data for Name: EquipmentSlot; Type: TABLE DATA; Schema: public; Owner: ro
--

INSERT INTO public."EquipmentSlot" (id, "buildId", location, "refineLevel", "itemId", "card1Id", "card2Id", "card3Id", "card4Id") VALUES ('0f7cee5e-02b6-4b66-b259-d1c2824d370d', '4c9cd9e6-3a92-4321-ab6c-a1a302887814', 'WEAPON', 7, 1101, 4001, NULL, NULL, NULL);
INSERT INTO public."EquipmentSlot" (id, "buildId", location, "refineLevel", "itemId", "card1Id", "card2Id", "card3Id", "card4Id") VALUES ('264f4498-f29c-4749-a513-6d81a85a1f61', '4c9cd9e6-3a92-4321-ab6c-a1a302887814', 'HEAD_TOP', 4, 5001, NULL, NULL, NULL, NULL);
INSERT INTO public."EquipmentSlot" (id, "buildId", location, "refineLevel", "itemId", "card1Id", "card2Id", "card3Id", "card4Id") VALUES ('ba255189-346e-4092-8de2-d5343ccec030', 'f6d5509a-dc32-405d-8912-0e314612aeed', 'WEAPON', 7, 1101, 4002, NULL, NULL, NULL);
INSERT INTO public."EquipmentSlot" (id, "buildId", location, "refineLevel", "itemId", "card1Id", "card2Id", "card3Id", "card4Id") VALUES ('b713a2c8-a9df-4634-a75f-4c46d791f217', '908061bc-37ab-41e3-adcc-358b2b0fcbf8', 'HEAD_TOP', 0, 5001, NULL, NULL, NULL, NULL);


--
-- PostgreSQL database dump complete
--

\unrestrict gM7UQuaVvkMIfBbRWfAecQEpcaU04vYSMJcmsWflJnNrkl42QaszBO0bEDohbs5

