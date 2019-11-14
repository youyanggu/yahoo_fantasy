from collections import defaultdict
import datetime
import logging

from yahoo_oauth import OAuth2

oauth_logger = logging.getLogger('yahoo_oauth')
oauth_logger.disabled = True

oauth = OAuth2(None, None, from_file='oauth2.json')
if not oauth.token_is_valid():
    oauth.refresh_access_token()

#resp = oauth.session.get('https://fantasysports.yahooapis.com/fantasy/v2/users;use_login=1/games;game_keys=nfl/leagues?format=json')
#print(resp.text)
LEAGUE_KEY = '390.l.1079029'
LEAGUE_ID = '1079029'

def get_transactions():
    # returns transactions in chronologically increasing order
    print('Getting transactions...')
    url = 'https://fantasysports.yahooapis.com/fantasy/v2/league/{}/transactions?format=json'.format(LEAGUE_KEY)
    resp = oauth.session.get(url)
    print(resp)

    data = resp.json()
    transacts = data['fantasy_content']['league'][1]['transactions']
    assert transacts['count'] == len(transacts)-1, 'expecting count key'
    num_transacts = transacts.pop('count')
    print('Num transactions: {}'.format(num_transacts))

    # transacts is a dict with string int keys, so we convert that to an arr
    transacts_arr = []
    for i in range(len(transacts)):
        transacts_arr.append(transacts[str(i)])
    assert len(transacts_arr) == num_transacts
    return transacts_arr[::-1]

def parse_add_drop(transact, transacts_clean):
    t = transact['transaction']
    assert t[1]['players']['count'] == 2
    assert len(t[1]['players']['0']['player'][1]) == 1
    assert t[1]['players']['0']['player'][1]['transaction_data'][0]['type'] == 'add'
    assert len(t[1]['players']['1']['player'][1]) == 1
    assert t[1]['players']['1']['player'][1]['transaction_data']['type'] == 'drop'

    ts = datetime.datetime.fromtimestamp(int(t[0]['timestamp']))
    player_add = t[1]['players']['0']['player'][0][2]['name']['full']
    faab_bid = int(t[0].get('faab_bid', 0))
    manager_add = t[1]['players']['0']['player'][1]['transaction_data'][0]['destination_team_name']
    player_drop = t[1]['players']['1']['player'][0][2]['name']['full']
    manager_drop = t[1]['players']['1']['player'][1]['transaction_data']['source_team_name']
    assert manager_add == manager_drop

    add_clean = {
        'id' : len(transacts_clean),
        'type' : 'add',
        'player' : player_add,
        'faab' : faab_bid,
        'manager' : manager_add,
        'ts' : ts,
    }
    transacts_clean.append(add_clean)
    drop_clean = {
        'id' : len(transacts_clean),
        'type' : 'drop',
        'player' : player_drop,
        'manager' : manager_drop,
        'ts' : ts,
    }
    transacts_clean.append(drop_clean)

def parse_add(transact, transacts_clean):
    t = transact['transaction']
    assert t[1]['players']['count'] == 1
    assert len(t[1]['players']['0']['player'][1]) == 1
    assert t[1]['players']['0']['player'][1]['transaction_data'][0]['type'] == 'add'

    ts = datetime.datetime.fromtimestamp(int(t[0]['timestamp']))
    player_add = t[1]['players']['0']['player'][0][2]['name']['full']
    faab_bid = int(t[0].get('faab_bid', 0))
    manager_add = t[1]['players']['0']['player'][1]['transaction_data'][0]['destination_team_name']

    add_clean = {
        'id' : len(transacts_clean),
        'type' : 'add',
        'player' : player_add,
        'faab' : faab_bid,
        'manager' : manager_add,
        'ts' : ts,
    }
    transacts_clean.append(add_clean)

def parse_drop(transact, transacts_clean):
    t = transact['transaction']
    assert t[1]['players']['count'] == 1
    assert len(t[1]['players']['0']['player'][1]) == 1
    assert t[1]['players']['0']['player'][1]['transaction_data']['type'] == 'drop'

    ts = datetime.datetime.fromtimestamp(int(t[0]['timestamp']))
    player_drop = t[1]['players']['0']['player'][0][2]['name']['full']
    manager_drop = t[1]['players']['0']['player'][1]['transaction_data']['source_team_name']

    drop_clean = {
        'id' : len(transacts_clean),
        'type' : 'drop',
        'player' : player_drop,
        'manager' : manager_drop,
        'ts' : ts,
    }
    transacts_clean.append(drop_clean)

def print_player_to_adds(transacts_clean):
    print('-------------------------------------')
    print('print_player_to_adds')
    print('-------------------------------------')
    player_to_adds = defaultdict(list) # list of faab bids
    for transact in transacts_clean:
        if transact['type'] == 'add':
            player_to_adds[transact['player']].append(transact['faab'])
    sort_by = 'num_adds' # faab or num_adds
    if sort_by == 'num_adds':
        key = lambda x: (len(player_to_adds[x]), sum(player_to_adds[x]))
    elif sort_by == 'faab':
        key = lambda x: (sum(player_to_adds[x]), len(player_to_adds[x]))
    for k in sorted(player_to_adds, reverse=True, key=key):
        print('{:<20s} - Adds: {} - FAAB: ${:.0f} - {}'.format(
            k, len(player_to_adds[k]), sum(player_to_adds[k]), player_to_adds[k]))
    print('')

def faabs_for_player(player, transacts):
    faabs = []
    for transact in transacts:
        if transact['player'] == player and transact['type'] == 'add':
            faabs.append(transact.get('faab', 0))
    return faabs

def faab_from_player_drops(transacts_clean, summary=False):
    print('-------------------------------------')
    print('faab_from_player_drops')
    print('-------------------------------------')
    manager_to_players_dropped = defaultdict(list)
    manager_player_dict = {}
    manager_to_num_drops = defaultdict(int)
    for i in range(len(transacts_clean)):
        transact = transacts_clean[i]
        if transact['type'] == 'drop':
            faabs = faabs_for_player(transact['player'], transacts_clean[i+1:])
            manager_to_num_drops[transact['manager']] += 1
            if (transact['manager'], transact['player']) not in manager_player_dict:
                manager_to_players_dropped[transact['manager']].append(
                    (transact['player'], faabs))
                manager_player_dict[(transact['manager'], transact['player'])] = True
    
    # get sort order
    manager_to_faab_spent_on_dropped_players = {}
    for manager, players_dropped in list(manager_to_players_dropped.items()):
        faabs_sum = 0
        for player_dropped in sorted(players_dropped):
            player, faabs = player_dropped
            if sum(faabs) > 0:
                faabs_sum += sum(faabs)
        manager_to_faab_spent_on_dropped_players[manager] = faabs_sum

    for manager in sorted(manager_to_faab_spent_on_dropped_players,
                          key=lambda x: manager_to_faab_spent_on_dropped_players[x], reverse=True):
        players_dropped = manager_to_players_dropped[manager]
        if summary:
            print u'{:<25s} - {:<2s} drops - ${:.0f}'.format(
                manager, str(manager_to_num_drops[manager]), manager_to_faab_spent_on_dropped_players[manager])
        else:
            print('-----------------------')
            print(manager)
            print('Num drops: {}'.format(manager_to_num_drops[manager]))
            print('Total FAAB spent on dropped players: ${:.0f}'.format(
                manager_to_faab_spent_on_dropped_players[manager]))
            faabs_sum = 0
            for player_dropped in sorted(players_dropped, key=lambda x: sum(x[1]), reverse=True):
                player, faabs = player_dropped
                assert sum(faabs) >= 0, faabs
                if sum(faabs) > 0:
                    faabs_sum += sum(faabs)
                    print(player, faabs)
    print('')

def search_for_drops(player, transacts):
    # return True if player is dropped
    for transact in transacts:
        if transact['player'] == player and transact['type'] == 'drop':
            return True
    return False

def good_adds(transacts_clean):
    print('-------------------------------------')
    print('good_adds - players added that have not been dropped')
    print('-------------------------------------')
    manager_to_players = defaultdict(list)
    for i in range(len(transacts_clean)):
        transact = transacts_clean[i]
        if (datetime.datetime.now() - transact['ts']) < datetime.timedelta(days=7):
            # if added for less than 7 days, we ignore
            continue
        if transact['type'] == 'add':
            if not search_for_drops(transact['player'], transacts_clean[i+1:]):
                # player still on roster
                manager_to_players[transact['manager']].append(transact['player'])
    for manager, players_arr in sorted(manager_to_players.items()):
        print(u'{:<25s} - {}'.format(manager, players_arr))
    print('')

def top_adds(transacts_clean):
    print('-------------------------------------')
    print('top_adds - highest FAAB spent per manager')
    print('-------------------------------------')
    manager_to_top_player = {}
    for i in range(len(transacts_clean)):
        transact = transacts_clean[i]
        if transact['type'] == 'add':
            if transact['manager'] not in manager_to_top_player:
                manager_to_top_player[transact['manager']] = (transact['player'], transact.get('faab', 0))
            else:
                if transact.get('faab', 0) > manager_to_top_player[transact['manager']][1]:
                    manager_to_top_player[transact['manager']] = (transact['player'], transact.get('faab', 0))
    for manager, player in sorted(list(manager_to_top_player.items()),
                                  key=lambda x: x[1][1], reverse=True):
        print(u'{:<25s} - ${:.0f} - {}'.format(manager, player[1], player[0]))
    print('')

def clean_add_drops(transacts_arr):
    transacts_clean = []
    for transact in transacts_arr:
        transact_type = transact['transaction'][0]['type']
        if transact_type == 'add/drop':
            parse_add_drop(transact, transacts_clean)
        elif transact_type == 'add':
            parse_add(transact, transacts_clean)
        elif transact_type == 'drop':
            parse_drop(transact, transacts_clean)
    return transacts_clean

def main():
    print(datetime.datetime.now())
    transacts_arr = get_transactions()
    transacts_clean = clean_add_drops(transacts_arr)
    print_player_to_adds(transacts_clean)
    faab_from_player_drops(transacts_clean)
    good_adds(transacts_clean)
    top_adds(transacts_clean)

if __name__ == '__main__':
    main()
