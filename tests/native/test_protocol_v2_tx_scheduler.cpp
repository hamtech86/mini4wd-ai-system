#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <vector>
#include "../../firmware/motor/ProtocolV2TxScheduler.h"
using namespace mini4wd310;
struct FakeSerial {
  int capacity; std::vector<uint8_t> bytes; std::vector<size_t> chunks;
  explicit FakeSerial(int c):capacity(c){}
  int availableForWrite() const { return capacity; }
  size_t write(const uint8_t* p,size_t n){chunks.push_back(n);bytes.insert(bytes.end(),p,p+n);return n;}
};
static std::vector<uint8_t> expected(const DeviceReplyV2& r){
  uint8_t b[kMaxWireSize]={0}; memcpy(b+1+kHeaderSize,r.payload,r.payload_length);
  uint16_t n=0; assert(encode_frame_in_place(r.message_type,r.session_uuid,r.epoch_tag,r.command_id,b,r.payload_length,sizeof(b),&n));
  return std::vector<uint8_t>(b,b+n);
}
static void drain(ProtocolV2TxScheduler& tx,FakeSerial& s){
  for(int i=0;i<100 && tx.busy();++i) tx.service(s);
  assert(!tx.busy());
}
int main(){
  ProtocolV2TxScheduler tx; FakeSerial s(5);
  DeviceReplyV2 first; memset(&first,0,sizeof(first));
  first.valid=true; first.message_type=ERROR_MSG; first.command_id=0;
  first.payload_length=8; first.payload[0]=1; first.payload[1]=PWM_SET; write_u32(first.payload+4,1);
  assert(tx.enqueue(first)); tx.service(s); assert(s.bytes.size()==5 && tx.busy());
  DeviceReplyV2 low=first; low.payload[0]=2; assert(tx.enqueue(low));
  DeviceReplyV2 stop; memset(&stop,0,sizeof(stop));
  stop.valid=true; stop.message_type=STOP_ACK; stop.session_uuid[0]=1;
  stop.epoch_tag=1; stop.command_id=3; stop.payload_length=3;
  stop.payload[0]=0; stop.payload[1]=0; stop.payload[2]=2;
  assert(tx.enqueue(stop));
  const std::vector<uint8_t> a=expected(first), b=expected(stop);
  s.capacity=64; drain(tx,s);
  std::vector<uint8_t> joined=a; joined.insert(joined.end(),b.begin(),b.end());
  assert(s.bytes==joined);
  for(size_t i=0;i<s.chunks.size();++i) assert(s.chunks[i]<=16);
  return 0;
}
