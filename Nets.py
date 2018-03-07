import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.nn.init as I
from torch.autograd import Variable


class EmbedAttention(nn.Module):

    def __init__(self, att_size):
        super(EmbedAttention, self).__init__()
        self.att_w = nn.Linear(att_size,1,bias=False)

    def forward(self,input,len_s):
        att = self.att_w(input).squeeze(-1)
        out = self._masked_softmax(att,len_s).unsqueeze(-1)
        return out
        
    
    def _masked_softmax(self,mat,len_s):
        
        len_s = torch.FloatTensor(len_s).type_as(mat.data).long()
        idxes = torch.arange(0,int(len_s[0]),out=mat.data.new(int(len_s[0])).long()).unsqueeze(1)
        mask = Variable((idxes<len_s.unsqueeze(0)).float(),requires_grad=False)

        exp = torch.exp(mat) * mask
        sum_exp = exp.sum(0,True)+0.0001
     
        return exp/sum_exp.expand_as(exp)



class AttentionalBiRNN(nn.Module):

    def __init__(self, inp_size, hid_size, dropout=0, RNN_cell=nn.GRU):
        super(AttentionalBiRNN, self).__init__()
        
        self.natt = hid_size*2

        self.rnn = RNN_cell(input_size=inp_size,hidden_size=hid_size,num_layers=1,bias=True,batch_first=True,dropout=dropout,bidirectional=True)
        self.lin = nn.Linear(hid_size*2,self.natt)
        self.att_w = nn.Linear(self.natt,1,bias=False)
        self.emb_att = EmbedAttention(self.natt)

    
    def forward(self, packed_batch):
        
        rnn_sents,_ = self.rnn(packed_batch)
        enc_sents,len_s = torch.nn.utils.rnn.pad_packed_sequence(rnn_sents)

        emb_h = F.tanh(self.lin(enc_sents))

        attended = self.emb_att(emb_h,len_s) * enc_sents
        return attended.sum(0,True).squeeze(0)




class HAN(nn.Module):

    def __init__(self, ntoken, num_class, emb_size=200, hid_size=50):
        super(HAN, self).__init__()

        self.emb_size = emb_size
        self.embed = nn.Embedding(ntoken, emb_size,padding_idx=0)
        self.word = AttentionalBiRNN(emb_size, hid_size)
        self.sent = AttentionalBiRNN(hid_size*2, hid_size)
        self.lin_out = nn.Linear(hid_size*2,hid_size*2)
        self.lin_out1 = nn.Linear(hid_size*2,hid_size*2)
        self.lin_out2 = nn.Linear(hid_size*2,num_class)

    def set_emb_tensor(self,emb_tensor):
        self.emb_size = emb_tensor.size(-1)
        self.embed.weight.data = emb_tensor

    
    def _reorder_sent(self,sents,sent_order):
        
        sents = F.pad(sents,(0,0,1,0)) #adds a 0 to the top
        revs = sents[sent_order.view(-1)]
        revs = revs.view(sent_order.size(0),sent_order.size(1),sents.size(1))

        return revs
 

    def forward(self, batch_reviews,sent_order,ls,lr):

        emb_w = F.dropout(self.embed(batch_reviews),training=self.training)
        packed_sents = torch.nn.utils.rnn.pack_padded_sequence(emb_w, ls,batch_first=True)
        sent_embs = self.word(packed_sents)
        rev_embs = self._reorder_sent(sent_embs,sent_order)
        packed_rev = torch.nn.utils.rnn.pack_padded_sequence(rev_embs, lr,batch_first=True)
        doc_embs = self.sent(packed_rev)
        out = F.alpha_dropout(self.lin_out(F.selu(doc_embs)))
        out = F.alpha_dropout(self.lin_out1(F.selu(doc_embs)))
        out = self.lin_out2(F.selu(out))

        return out


class EmbedAttention2(nn.Module):

    def __init__(self, att_size):
        super(EmbedAttention2, self).__init__()
        self.att_w = nn.Linear(att_size,1,bias=False)

    def forward(self,input,len_s):
        att = self.att_w(input).squeeze(-1)
        out = self._masked_softmax(att,len_s).unsqueeze(-1)
        return out
        
    
    def _masked_softmax(self,mat,len_s):
        len_s = len_s.data
        max_v = torch.max(len_s)
        #len_s = torch.FloatTensor(len_s).type_as(mat.data).long()
        idxes = torch.arange(0,int(max_v),out=mat.data.new(int(max_v)).long()).unsqueeze(0)


        mask = Variable((idxes<len_s.unsqueeze(1)).float(),requires_grad=False)


        exp = torch.exp(mat) * mask
        sum_exp = exp.sum(1,True)+0.0001
     
        return exp/sum_exp.expand_as(exp)


class AttentionalBiRNN2(nn.Module):

    def __init__(self, inp_size, hid_size, dropout=0, RNN_cell=nn.GRU):
        super(AttentionalBiRNN2, self).__init__()
        
        self.natt = hid_size*2

        self.rnn = RNN_cell(input_size=inp_size,hidden_size=hid_size,num_layers=1,bias=True,batch_first=True,dropout=dropout,bidirectional=True)
        self.lin = nn.Linear(hid_size*2,self.natt)
        self.att_w = nn.Linear(self.natt,1,bias=False)
        self.emb_att = EmbedAttention2(self.natt)

    
    def forward(self, batch,len_s):
        
        rnn_sents,_ = self.rnn(batch)
        emb_h = F.tanh(self.lin(rnn_sents))

        attended = self.emb_att(emb_h,len_s) * rnn_sents
        
        return attended.sum(1)




class CWAN(nn.Module):

    def __init__(self, ntoken, num_class, emb_size=200, hid_size=100):
        super(CWAN, self).__init__()

        self.emb_size = emb_size
        self.embed = nn.Embedding(ntoken, emb_size,padding_idx=0)
        self.word = AttentionalBiRNN2(emb_size, hid_size)
        self.lin_out = nn.Linear(hid_size*2,num_class)
        self.rnn = nn.GRU(input_size=emb_size,hidden_size=emb_size,num_layers=1,bias=True,batch_first=True,dropout=0,bidirectional=False)


    def set_emb_tensor(self,emb_tensor):
        self.emb_size = emb_tensor.size(-1)
        self.embed.weight.data = emb_tensor

    
    def _reorder_sent(self,sents,sent_order):
        
        sents = F.pad(sents,(0,0,1,0)) #adds a 0 to the top
        revs = sents[sent_order.view(-1)]
        revs = revs.view(sent_order.size(0),sent_order.size(1),sents.size(1))

        return revs
 

    def forward(self, txt,we,wi,lens):

        emb_w = F.dropout(self.embed(txt),training=self.training)
        packed_sents = torch.nn.utils.rnn.pack_padded_sequence(emb_w, lens,batch_first=True)
        rnn_out,_ = self.rnn(packed_sents)
        enc_tweets,_ = torch.nn.utils.rnn.pad_packed_sequence(rnn_out)
        enc_tweets = enc_tweets.transpose(0,1).contiguous()
        
        enc_tweets = enc_tweets.view(-1,enc_tweets.size(-1))
        enc_tweets = F.pad(enc_tweets,(0,0,1,0)) #adds a 0 to the top
        try:
            w_tweets = enc_tweets[wi.view(-1)]
        except Exception as e:
            
            print(enc_tweets.size())
            print(wi)
            raise e

        w_tweets = w_tweets.view(txt.size(0),-1,enc_tweets.size(-1))
        
        attended = self.word(w_tweets,torch.sum(we,dim=-1))

        # len_t,i = torch.sort(torch.sum(we,dim=-1),descending=True)
        # print(len_t)
        
        # w_tweets = w_tweets[i]
        # packed_sents = torch.nn.utils.rnn.pack_padded_sequence(w_tweets, len_t.tolist(),batch_first=True)
        

        out = self.lin_out(F.dropout(F.tanh(attended)))
        
        

        #sent_embs = self.word(packed_sents)
        # rev_embs = self._reorder_sent(sent_embs,sent_order)
        # packed_rev = torch.nn.utils.rnn.pack_padded_sequence(rev_embs, lr,batch_first=True)
        # doc_embs = self.sent(packed_rev)
        # out = F.alpha_dropout(self.lin_out(F.selu(doc_embs)))
        # out = F.alpha_dropout(self.lin_out1(F.selu(doc_embs)))
        # out = self.lin_out2(F.selu(out))

        return out
