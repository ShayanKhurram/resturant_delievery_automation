
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph, START, END
import asyncio
from typing_extensions import TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from langchain_mcp_adapters.client import MultiServerMCPClient
import requests

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from prisma import Prisma




from dotenv import load_dotenv

load_dotenv()

model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
)

# Both agents will work on this model

class State(TypedDict):
    input :str
    order_id: int
    rider_name: str
    rider_id: int 
    order_info: str
    order_address: str
    order_owner_number:int
    rider_number:int
    order_status: str
    rider_reply : str
    avoid_riders  : list[int] = []


class Order(BaseModel):
    # need to get these from db mcp
    order_id: int
    order_info: str
    order_address: str
    order_owner_number:int

class Rider(BaseModel):
     rider_id : int
     rider_name : str
     rider_number :int    

class Rider_reply(BaseModel):
      rider_reply :str



Orderhandler_workflow = StateGraph(State)




client = MultiServerMCPClient(
    {
        "db" : {
            "command" : "npx",
            "args" : ["-y","@supabase/mcp-server-supabase@latest", "--read-only","--project-ref=jkcbcojlshhcuqxaitbs"],
            "transport" : "stdio",
            "env" : {
                "SUPABASE_ACCESS_TOKEN":"sbp_1246abde249242cf5fcc85a91a0293eeb9d203ff"
            }
        } ,
        "whatsapp" : {
              "command" : "python",
              "args" : ["C:/Users/shani/OneDrive/Desktop/Mcp_making/whatsapp-mcp/whatsapp-mcp-server/main.py"],
              "transport" : "stdio"
        }

    }
)


# app = FastAPI()
# @app.put("/webhooks/start_agent/{order_id}")
async def run_agent(order_id : int):
    
    
    tools = await client.get_tools()
    print(f"Available tools: {[tool.name for tool in tools]}")
    
    
      
    # order_handler workflow

    async def get_order_data(state : State):
            agent = create_react_agent(model=model, tools=tools,response_format= Order)
            prompt =  f"execute this sql query on order_data table. / SELECT *  FROM public.order_data WHERE order_id={order_id}; /"
            result = await agent.ainvoke({
                    "messages": [HumanMessage(content=prompt)]
                })
            data = result['structured_response']
            
            # updating the order state in db from incomplete to in-processing
             
            url=f"http://delievery-auto-server.onrender.com/webhook/order_placed/{state["order_id"]}"
            requests.put(url)


    # Update and return the state
            return  {
                "order_id": data.order_id,
                "order_info": data.order_info,
                "order_address": data.order_address,
                "order_owner_number": data.order_owner_number
                }
            
    async def get_rider_data(state :State):
            agent = create_react_agent(model=model, tools=tools,response_format= Rider)
            prompt = f"execute this sql query on riders table and it will give you  rider data. / Select * from public.riders WHERE rider_status = 'available'  and rider_id not in {state['avoid_riders']} ORDER BY RANDOM() LIMIT 1;"    
            result = await agent.ainvoke({
                    "messages": [HumanMessage(content=prompt)]
                })
            data = result['structured_response']
            r=data.rider_id
            url = f"http://delievery-auto-server.onrender.com/webhook/rider_status/{r}"
            requests.put(url)
           
            return {
                 
                 "rider_id" : data.rider_id,
                 "rider_name" : data.rider_name,
                 "rider_number" : data.rider_number
            }    
    
    async def ask_rider_availaiblity(state :State):
            agent = create_react_agent(model=model, tools=tools)
            prompt = f"""
            use the send_message tool to send the whatsapp message to a phone number mentioned below
                Send this WhatsApp message: 
                phone_no : 923302000091
                Message: "Hi  , are you up for delievry plz reply with yes or no"
                
                """
             # Print the conversation for debugging
            
            result = await agent.ainvoke({
                    "messages": [HumanMessage(content=prompt)]
                })
         
            return result
           
                
   
   
   
    async def get_rider_reply(state:State):

                prompt = f"use the get_message tool to get our  latest conversation  with rider the rider phone no is 923302000091 his reply can  be yes or no or  may be he hasnt replied yet  evaluate his response with one word "
                agent = create_react_agent(model=model,tools=tools,response_format=Rider_reply)
               
        #   we are gonna wait for five minutes 
          
                
                await asyncio.sleep(30)
                response = await agent.ainvoke({
                    "messages": [HumanMessage(content=prompt)]
                })
                data = response['structured_response']
                rider_answer =  data.rider_reply
                
                if rider_answer.lower() == "no":
                      state["avoid_riders"].append(state["rider_id"])
                      return   {"rider_reply" : "no"}
                      
                if rider_answer.lower() == "yes":
                      return    { "rider_reply" : "yes"}
                      
                

                return { "rider_reply" : "not replied" }
      
    #   if its yes than we need to go to customer informing their order has been picked   (we ought to make sure that mf rider dosent get picked again )
    #   if its no than we need to pick another rider 
    #   if it hasnt been replied we need to pickup another rider
    

    async def inform_order_owner(state : State):
          prompt=f"""
          Send this message to this phone no 923302000091
          
          message : Your Order has been picked up by our rider 
            rider name :  {state["rider_name"]}
            rider number : {state['rider_number']}
            order id  : {state['order_id']}
            order info  : {state['order_info']}


          """
          agent = create_react_agent(model=model, tools=tools)
          response = await agent.ainvoke({
                    "messages": [HumanMessage(content=prompt)]
                })
          
        # updating rider and order state in db 
          url_rider = f"http://delievery-auto-server.onrender.com/webhook/agent_ended_rider_updation/{state["rider_id"]}"
          url_order = f"http://delievery-auto-server.onrender.com/webhook/update_agent_ended_order_updation/{state["order_id"]}"
          requests.put(url_order)
          requests.put(url_rider)


          return {}
          
    async def route_riders_reply(state  :State):
          if state["rider_reply"] == "yes":
                return "yes"
          elif state["rider_reply"] == "no":
                return "no" 
          else:
                "no reply"  

    # node creation
    Orderhandler_workflow.add_node("get_order_data",get_order_data)
    Orderhandler_workflow.add_node("get_rider_data",get_rider_data)
    Orderhandler_workflow.add_node("ask_rider_availaiblity",ask_rider_availaiblity)
    Orderhandler_workflow.add_node("get_rider_reply",get_rider_reply)
    Orderhandler_workflow.add_node("inform_order_owner",inform_order_owner)



    # edge creation
    Orderhandler_workflow.add_edge(START,"get_order_data")
    Orderhandler_workflow.add_edge("get_order_data","get_rider_data")
    Orderhandler_workflow.add_edge("get_rider_data","ask_rider_availaiblity")
    Orderhandler_workflow.add_edge("ask_rider_availaiblity","get_rider_reply")
    Orderhandler_workflow.add_conditional_edges(
          "get_rider_reply",
          route_riders_reply,
          {
                "yes" : "inform_order_owner",
                "no" :   "get_rider_data",
                "no reply" : "get_rider_data"
          },

    )
    Orderhandler_workflow.add_edge("inform_order_owner",END)

    chain = Orderhandler_workflow.compile()


   
    
    
          
    agent_response = await chain.ainvoke({ 
               "order_id" : order_id  ,
               "avoid_riders": []
         }) 
    
    return agent_response
    

    
    

if __name__ == "__main__":
    result = asyncio.run(run_agent(4))
    print(result)  
      
    
    
    
         
            
    


   

