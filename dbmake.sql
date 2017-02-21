CREATE TABLE user_data
(
    racer_id integer,
	discord_id bigint,
	discord_name text,
	twitch_name VARCHAR(25),
	timezone text,
	PRIMARY KEY (racer_id),
    UNIQUE (discord_id),
    UNIQUE (twitch_name)
);
    
CREATE TABLE match_data
(
	racer_1_id int NOT NULL,
	racer_2_id int NOT NULL,
	week_number int,
	timestamp bigint DEFAULT 0,
	racer_1_wins int DEFAULT 0,
	racer_2_wins int DEFAULT 0,
	draws int DEFAULT 0,
	noplays int DEFAULT 0,
	cancels int DEFAULT 0,
	flags int DEFAULT 0,
	league int DEFAULT 0,
	number_of_races int DEFAULT 0,
	cawmentator_id int DEFAULT 0,
	PRIMARY KEY (racer_1_id, racer_2_id, week_number),
    FOREIGN KEY (racer_1_id) REFERENCES user_data(racer_id),
    FOREIGN KEY (racer_2_id) REFERENCES user_data(racer_id)
);
  
CREATE TABLE channel_data
(
    channel_id int,
	racer_1_id int NOT NULL,
	racer_2_id int NOT NULL,
	week_number int,
	PRIMARY KEY (channel_id),
    FOREIGN KEY match_id (racer_1_id, racer_2_id, week_number) REFERENCES match_data (racer_1_id, racer_2_id, week_number)
);

CREATE TABLE race_data
(
	racer_1_id int NOT NULL,
	racer_2_id int NOT NULL,
	week_number int,
	race_number int,
	timestamp bigint,
	seed int,
	racer_1_time int,
	racer_2_time int,
	winner int DEFAULT -1,
	contested int DEFAULT 0,
	flags int DEFAULT 0,
	PRIMARY KEY (racer_1_id, racer_2_id, week_number, race_number),
    FOREIGN KEY match_id (racer_1_id, racer_2_id, week_number) REFERENCES match_data (racer_1_id, racer_2_id, week_number)
);