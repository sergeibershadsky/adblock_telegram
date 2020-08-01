## AdBlockTelegram

### Installation

Copy template env file and fill out the variables according to this [guide](https://docs.telethon.dev/en/latest/basic/signing-in.html#signing-in)
```bash
cp .env.example .env
```



Install all the dependencies
```bash
pip3 install -r requirements.txt
```

And run
```bash
python app.py
```

Add records by hand (as for now)
```sqlite
INSERT INTO channel (name, blaklist_words) VALUES ('telegram', 'adword1,adword2,adword3'); 
```
