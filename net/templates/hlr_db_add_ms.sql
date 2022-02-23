/* Use this file to add the subscriber for MS_RUN_IN_OSMO_DEV=1 to your hlr.db:
 *   sqlite3 -batch hlr.db < hlr_db_add_ms.sql
 */

INSERT INTO subscriber (id, imsi, msisdn)
VALUES (${MS_SUBSCR_ID}, "${MS_IMSI}", "${MS_MSISDN}");

INSERT INTO auc_2g (subscriber_id, algo_id_2g, ki)
VALUES (${MS_SUBSCR_ID}, 1 /* OSMO_AUTH_ALG_COMP128v1 */,
	REPLACE("${MS_KI}", " ", ""));
