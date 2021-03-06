import socket
import stół
import pygame
import pygame.locals
import klient
from _thread import *
import sys
import os
import mysql.connector
import traceback


class Serwer:
    """ Klasa odpowiadająca za stworzenie serwera do gry w Ponga """
    def __init__(self, ip, port):
        """
        In
        ---
        ip
            adress IP, na którym zostanie postawiony serwer
        port
            numer portu, na którym zostanie postawiony serwer
        """
        self.ip = ip
        self.port = 5555
        self.klienci = []
        self.włączony = True
        self.stoły = {}
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.s.bind((ip, port))
        except socket.error as e:
            str(e)
        # niezbędne dane do połączenia z bazą danych
        self.mydb = mysql.connector.connect(
            host="localhost",
            user="server",
            passwd="zaq1@WSX",
            database="pong"
            )

    def wyłącz(self):
        """Powiadamia klientów o przerwaniu pracy serwera i wyłącza serwer"""
        import os
        while self.klienci:
            self.klienci[0].rozłącz("SerwerWyłączony")
        os._exit(1)
        exit()
        self.s.close()
        self.s.shutdown()

    def zaloguj(self, dane):
        """
        Przeszukuje bazę danych w celu sprawdzenia
        czy dany użytkownik może się zalogować

        In
        ---
        dane - tablica [login, hasło]

        Out
        ---
        None - jeśli nie ma takiego użytkownika
        Numer id użytkownika - jeśli zalogowanie przebiegło pomyślnie

        """

        mycursor = self.mydb.cursor()
        print("Próba zalogowania:", dane)
        if len(dane) < 2:
            return None
        print(dane)
        mycursor.execute(f"SELECT id FROM users WHERE\
            login=\"{dane[0]}\" AND password=\"{dane[1]}\";")

        myresult = mycursor.fetchall()

        if myresult:
            print(myresult)
            return myresult[0][0]
        else:
            return None

    def zarejestruj(self, dane):
        """Wstawia do bazy danych nowego użytkownika
        In
        ---
        dane - tablica [login, hasło]

        Out
        ---
        Numer id użytkownika 
        """
        mycursor = self.mydb.cursor()

        sql = "INSERT INTO users (login, password) VALUES (%s, %s)"
        val = tuple(dane)
        mycursor.execute(sql, val)

        self.mydb.commit()

        print("1 record inserted, ID:", mycursor.lastrowid)
        return mycursor.lastrowid

    def zapisz_wynik(self, dane):
        """ Wstawia do bazy wynik rozegranego meczu
        In
        ---
        dane - [nick1, nick2, punkty1, punkty2, zwyciężca]
        """
        try:
            mycursor = self.mydb.cursor()
        except:
            self.mydb = mysql.connector.connect(
                host="localhost",
                user="server",
                passwd="zaq1@WSX",
                database="pong"
                )
            mycursor = self.mydb.cursor()

        sql = "INSERT INTO scores (player1, player2, score1, score2, winner)\
             VALUES (%s, %s, %s, %s, %s)"
        val = tuple(dane)
        mycursor.execute(sql, val)

        self.mydb.commit()

        print("1 record inserted, ID:", mycursor.lastrowid)
        return mycursor.lastrowid

    def ranking(self, nick):
        """
        Wysyła zapytanie do bazy danych o numer gracza w rankingu

        In
        ---
        nick

        Out
        ---
        Miejsce w rankingu
        """
        try:
            mycursor = self.mydb.cursor()
        except:
            self.mydb = mysql.connector.connect(
                host="localhost",
                user="server",
                passwd="zaq1@WSX",
                database="pong"
                )
            mycursor = self.mydb.cursor()

        mycursor.execute("select winner, count(winner) as wins \
             from scores group by winner order by wins desc;")

        res = mycursor.fetchall()

        n = 1
        for i in res:
            if i[0] == nick:
                break
            n += 1

        if n > len(res):
            n = -1

        return str(n)

    def threaded_client(self, k):
        """
        Obsługa komuniktów wysyłanych przez klienta:
        wyloguj - wylogowywuje gracza
        zaloguj_login_hasło - loguje gracza
        zarejestruj_login_hasło - rejestruje gracza
        zrezygnuj - rezygnuje z gry podczas czegania na przeciwnika
        czekam - sprawdza czy nikt nie dołączył do stołu
        ustaw_x_y - zmienia pozycję rakiety na planszy
        piłeczka_w_h - aktualizuje pozycję piłki
        pobierzstoly - pobiera listę stołów
        stworzstol_numer - tworzy nowy stół
        dolacz_numer - dołącza do stołu
        nickprzeciwnika_numer - zwraca nick przeciwnika ze stołu
        ranking - zwraca miejsce w rankingu
        """
        import traceback
        k.wyślij("Connected")
        reply = ""

        gra = False
        user_id = None
        przeciwnik = None
        numer = None
        user_nick = None

        while True:
            try:
                data = k.połączenie.recv(2048)
                reply = data.decode("utf-8").lower()

                odpowiedź = "NieznaneZapytanie"

                # Wylogowanie, przypisanie zmiennym wartości początkowych
                if reply.startswith("wyloguj"):
                    gra = False
                    user_id = None
                    przeciwnik = None
                    numer = None
                    user_nick = None
                    k.wyślij("wylogowano")
                    continue

                # Obsługa logowania
                if not user_id:
                    dane = reply.split("_")[1:]
                    if reply.startswith("zaloguj"):
                        user_id = self.zaloguj(dane)
                    elif reply.startswith("zarejestruj"):
                        user_id = self.zarejestruj(dane)
                    if user_id:
                        mycursor = self.mydb.cursor()
                        query = f"SELECT login FROM \
                            users WHERE id=\"{user_id}\";"
                        mycursor.execute(query)
                        myresult = mycursor.fetchall()
                        user_nick = myresult[0][0]
                        odpowiedź = f"zalogowany_{user_id}"
                    else:
                        odpowiedź = "błądlogowania"

                # Obsługa gry
                elif gra:
                    # Rezygnacja z gry, np w trakcie oczekiwania na przeciwnika
                    if reply.startswith("zrezygnuj"):
                        self.stoły.pop(numer, None)
                        gra = False
                        odpowiedź = "zrezygnowano"
                    if przeciwnik:
                        przeciwnik.send(str.encode(reply))
                        odpowiedź = None

                    if reply.startswith("czekam"):
                        if not self.stoły[numer].czeka:
                            s = self.stoły[numer]
                            przeciwnik = s.przeciwnik(k.połączenie)
                            odpowiedź = "1"
                        else:
                            odpowiedź = "0"

                    # zmiana pozycji rakietki
                    elif reply.startswith("ustaw"):
                        x = float(reply.split("_")[1])
                        y = float(reply.split("_")[2])
                        if self.stoły[numer].gracz1 == k.połączenie:
                            self.stoły[numer].pozycja1 = (x, y)
                            self.stoły[numer].rakieta1.pozycja.x = x
                        else:
                            self.stoły[numer].pozycja2 = (x, y)
                            self.stoły[numer].rakieta2.pozycja.x = 800 - x - 80

                    # zmiana pozycji piłeczki
                    elif reply.startswith("piłeczka"):
                        szerokość = int(reply.split("_")[1])
                        wysokość = int(reply.split("_")[2])
                        s = self.stoły[numer]
                        p = (szerokość/ 2, wysokość/ 2)
                        s.piłeczka_pozycja_startowa = p
                        (x, y) = s.piłeczka_pozycja
                        x += s.prędkość_x
                        y += s.prędkość_y
                        s.piłeczka_pozycja = (x, y)
                        s.piłka.pozycja.x = x
                        s.piłka.pozycja.y = y
                        if s.piłeczka_pozycja[0] < 0 or s.piłeczka_pozycja[0] > szerokość:
                            s.prędkość_x *= -1 
                        if s.piłeczka_pozycja[1] < 0 or s.piłeczka_pozycja[1] > wysokość:
                            s.prędkość_y *= -1
                        # odbijanie od rakietki
                        if(s.piłka.pozycja.colliderect(s.rakieta1.pozycja) or
                           s.piłka.pozycja.colliderect(s.rakieta2.pozycja)):
                            if (s.piłka.pozycja.y < 100 and s.prędkość_y < 0
                                or s.piłka.pozycja.y  > 200 and s.prędkość_y > 0):

                                s.prędkość_y *= -1
                                print(f"1 pozycja_{self.stoły[numer].rakieta1.pozycja.x}_{self.stoły[numer].rakieta1.pozycja.y}\n\
                                2 pozycja_{self.stoły[numer].rakieta2.pozycja.x}_{self.stoły[numer].rakieta2.pozycja.y}\n\
                                p pozycja_{self.stoły[numer].piłka.pozycja.x}_{self.stoły[numer].piłka.pozycja.y}\n")
                        if s.piłeczka_pozycja[1] < 0:
                            s.score[0] += 1
                            self.reset_piłki(s)
                        elif s.piłeczka_pozycja[1] > wysokość:
                            s.score[1] += 1
                            self.reset_piłki(s)


                        # kończenie gry po uzyskaniu odpowiedniego wyniku

                        if s.score[0] == 3 or s.score[1] == 3:
                            gra = False
                            if s.score[0] == 3:
                                nick = s.gracz1_nick
                            else:
                                nick = s.gracz2_nick
                            k.wyślij(f"wygral_{nick}")
                            

                            if s.czeka == "wyszedl":
                                if numer in self.stoły:
                                    self.stoły.pop(numer, None)
                            else:
                                self.zapisz_wynik([s.gracz1_nick, s.gracz2_nick,
                                    s.score[0], s.score[1], nick])
                                s.czeka = "wyszedl"
                            
                            numer = None

                        # pomimo, że na serwerze zapisywane są wyniki i pozycja piłki jak dla pierwszego gracza
                        # drugi gracz powinien dostać je symetryczne
                        if s.gracz1 == k.połączenie:
                            odpowiedź = f"zmien.poz.pił_{s.piłeczka_pozycja}_{s.score}_"
                        else:
                            (x_pił,y_pił) = s.piłeczka_pozycja
                            zwracana_pozycja = (szerokość - x_pił, wysokość - y_pił)
                            zwracany_score = s.score[::-1]
                            odpowiedź = f"zmien.poz.pił_{zwracana_pozycja}_{zwracany_score}_"
                else:
                    # Pobieranie listy stołów
                    if reply.startswith("pobierzstoly"):
                        stoły = [str(i.numer) + ":1" if i.czeka
                            else str(i.numer) + ":0" for i in sorted(self.stoły.values(),
                                key = lambda i: i.numer)]
                        odpowiedź = "stoly_" + "_".join(stoły)

                    # Tworzenie nowego stołu
                    elif reply.startswith("stworzstol"):
                        numer = int(reply.split("_")[1])

                        if numer in self.stoły:
                            odpowiedź = f"stolistnieje"
                        else:
                            self.stoły[numer] = stół.Stół(numer, k.połączenie,user_nick)
                            odpowiedź = f"stol_{numer}:1"
                            odpowiedź = "stolutworzony"
                        gra = True

                    # Dołączanie do istniejącego stołu
                    elif reply.startswith("dolacz"):
                        numer = int(reply.split("_")[1])

                        if numer in self.stoły and self.stoły[numer].czeka:
                            self.stoły[numer].dołącz(k.połączenie)
                            odpowiedź = f"stol_{numer}:0"
                            przeciwnik = self.stoły[numer].przeciwnik(k.połączenie)
                            self.stoły[numer].gracz2_nick = user_nick
                        else:
                            odpowiedź = "stolnieistnieje"
                        gra = True

                # pobieranie nicku przeciwnika
                if reply.startswith("nickprzeciwnika"):
                    numer = int(reply.split("_")[1])
                    s = self.stoły[numer]
                    if user_nick == s.gracz1_nick:
                        odpowiedź = str(s.gracz2_nick)
                    else:
                        odpowiedź = str(s.gracz1_nick)

                #pobieranie pozycji rankigowej
                elif reply.startswith("ranking")  and user_nick:
                    odpowiedź = self.ranking(user_nick)


                if reply == "__shut_down__":
                    print("SHUT DOWN")
                    self.wyłącz()

                if odpowiedź:
                    k.wyślij(odpowiedź)

                if not data:
                    print("Disconnected")
                    break
                elif False:
                    print("From:",user_id)
                    print("Received: ", reply)
                    print("Sending : ", odpowiedź)
                    print("")

            except Exception:
                traceback.print_exc()
                break


        # Usunięcie gier, w których brał udział użytkownik.
        # Przy zerwaniu połączenia usuwa pozostawione gry.
        ### Uwaga, jeśli jeden gracz wyjdzie może powodować problemy po stronie 2 gracza
        ### (odwoływanie się do usuniętego elementu słownika)
        if k:
            for stol in self.stoły:
                if (self.stoły[stol].gracz1 == k.połączenie
                    or self.stoły[stol].gracz1 == k.połączenie):
                   self.stoły.pop(stol, None)
        print("Lost connection")
        k.rozłącz()
    
    def reset_piłki(self,stół):
        """ Resetuje pozycję piłki po zdobyciu punktu"""
        stół.piłeczka_pozycja = stół.piłeczka_pozycja_startowa

    def słuchaj(self):
        """ Uruchamia nasłuchiwanie klientów """
        self.s.listen()
        print("Waiting for a connection, Server Started")

        while True:
            try:
                conn, addr = self.s.accept()
                k = klient.Klient(conn, self) 
                print("Connected to:", addr)
                self.klienci.append(k)
                start_new_thread(Serwer.threaded_client, (self, k,))
            except OSError:
                pass