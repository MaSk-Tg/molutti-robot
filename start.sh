if [ -z $UPSTREAM_REPO ]
then
  echo "Cloning main Repository"
  git clone https://github.com/MaSk-Tg/molutti-robot /Charlie_Film_BoT
else
  echo "Cloning Custom Repo from $UPSTREAM_REPO "
  git clone $UPSTREAM_REPO /molutti-robot
fi
cd /molutti-robot
pip3 install -U -r requirements.txt
echo "Starting Bot....✅"
python3 bot.py
