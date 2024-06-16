import datetime
import os
from dotenv import find_dotenv, load_dotenv
import asyncio
import time
from telethon import TelegramClient
from telethon.tl.functions.channels import CreateChannelRequest, DeleteChannelRequest,InviteToChannelRequest
from telethon.tl.functions.messages import ExportChatInviteRequest

load_dotenv(find_dotenv())

api_id = os.getenv('api_id')
api_hash = os.getenv('api_hash')
phone = os.getenv('phone')



async def send_tg_message(client, channel_id, msg, img_path=None):
    try:
        if img_path:
            # Send an image to the channel
            await client.send_file(channel_id, img_path, caption=msg)
        else:
            # Send a message to the channel
            await client.send_message(channel_id, msg)
        print('Message and image sent to the channel')
    except Exception as e:
        print(f'Failed to send message or image: {e}')

async def create_tg_channel(client, new_title, new_about=""):
    try:
        result = await client(CreateChannelRequest(
            title=new_title,
            about=new_about,
            megagroup=False  # True if you want to create a supergroup instead of a channel
        ))

        print(f'Channel created with ID: {result.chats[0].id}')
        channel_id = result.chats[0].id
        # Convert the channel_id to a string to check its length
        channel_id_str = str(channel_id)

        # Determine the length and prepend accordingly
        if len(channel_id_str) == 10:
            negative_channel_id = int("-100" + channel_id_str)
        elif len(channel_id_str) == 11:
            negative_channel_id = int("-10" + channel_id_str)
        elif len(channel_id_str) == 12:
            negative_channel_id = int("-1" + channel_id_str)    
        else:
            raise ValueError("channel_id length is not supported")
        await send_tg_message(client, channel_id, "Welcome to Invest Trend")
        return negative_channel_id
    except Exception as e:
        print(f'Failed to create channel: {e}')
        return None

async def delete_tg_channel(client,channel_id):
    try:
        await client(DeleteChannelRequest(
            channel=channel_id
        ))
        print(f'Channel with ID {channel_id} deleted')
    except Exception as e:
        print(f'Failed to delete channel: {e}')
        
async def add_user_to_channel(client, channel_id, user_id):
    try:
        # Add user to the channel
        await client(InviteToChannelRequest(
            channel=channel_id,
            users=[user_id]
        ))
        print(f'User {user_id} added to channel {channel_id}')
    except Exception as e:
        print(f'Failed to add user: {e}')
        
async def generate_invite_link(client, channel_id):
    try:
        # Calculate the new expire date
        new_expire_date = datetime.datetime.now() + datetime.timedelta(days=365)
        
        result = await client(ExportChatInviteRequest(
            peer=channel_id,
            expire_date=new_expire_date
        ))
        invite_link = result.link
        print(f'Invite link generated: {invite_link}')
        return invite_link
    except Exception as e:
        print(f'Failed to generate invite link: {e}')
        return None

# async def main():
#     await client.start(phone)
#     await client.disconnect()

# # Ensure the client is started
# asyncio.run(main())

if __name__ == '__main__':
    
    loop2 = asyncio.get_event_loop()

    # Create the client and connect
    client = TelegramClient('test_it', api_id, api_hash)
    client.start(phone)

    channel_id = loop2.run_until_complete(create_tg_channel(client,"test","hihi"))
    print('channel_id: ', channel_id)
    print('channel_id: ', type(channel_id))
    print('channel_id: ', str(channel_id))
    
    # if channel_id:
    #     invite_link = loop2.run_until_complete(generate_invite_link(client, channel_id))
    #     print('invite_link: ', invite_link)
    #     if invite_link:
    #         loop2.run_until_complete(send_tg_message(client, "mattchunghk", f"Join the channel using this link: {invite_link}"))
        # loop2.run_until_complete(delete_tg_channel(client, channel_id))

    #2181320450 2189347676
    # channel_id = -1002194270039
    # loop2.run_until_complete(add_user_to_channel(client,channel_id,"mattchungcn"))
    loop2.run_until_complete(send_tg_message(client,channel_id,"hi you","./python/src/it.jpeg"))
    # time.sleep(3)
    # loop2.run_until_complete(delete_tg_channel(client,channel_id))